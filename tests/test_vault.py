"""راز از محیط یا انبار امن خوانده می‌شود؛ فایل و پیام خطا نباید آن را نگه دارند."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from rasam import config, vault


class MemoryBackend:
    def __init__(self):
        self.values = {}

    def get_password(self, service, name):
        return self.values.get((service, name))

    def set_password(self, service, name, value):
        self.values[service, name] = value

    def delete_password(self, service, name):
        del self.values[service, name]


def test_secret_round_trip_and_idempotent_delete(monkeypatch):
    backend = MemoryBackend()
    monkeypatch.setattr(vault, "_backend", lambda: backend)
    assert vault.write_secret("CONNECTION", "secret").ok
    result = vault.read_secret("CONNECTION")
    assert result.ok and result.value == "secret"
    assert "secret" not in repr(result)
    assert vault.delete_secret("CONNECTION").ok
    assert vault.delete_secret("CONNECTION").ok
    assert vault.read_secret("CONNECTION").value is None


def test_backend_errors_do_not_leak_the_secret(monkeypatch):
    def broken():
        raise OSError("password=very-secret")

    monkeypatch.setattr(vault, "_backend", broken)
    for result in (vault.read_secret("CONNECTION"), vault.write_secret("CONNECTION", "secret"),
                   vault.delete_secret("CONNECTION")):
        assert not result.ok and result.error
        assert "very-secret" not in result.error


def test_plaintext_backend_is_never_used(monkeypatch):
    monkeypatch.setattr(vault.keyring, "get_keyring", MemoryBackend)
    assert not vault.write_secret("CONNECTION", "secret").ok


@pytest.mark.parametrize("name", ["", "password=value", "../x", None])
def test_invalid_secret_names_are_rejected(name):
    assert not vault.write_secret(name, "secret").ok


def test_environment_wins_over_the_vault(monkeypatch):
    monkeypatch.setenv("RASAM_TEST_CONNECTION", "environment")
    monkeypatch.setattr(vault, "read_secret", lambda _: pytest.fail("must not read vault"))
    assert config.secret_value("TEST_CONNECTION") == "environment"


def test_vault_is_used_when_environment_is_missing(monkeypatch):
    monkeypatch.delenv("RASAM_TEST_CONNECTION", raising=False)
    monkeypatch.setattr(vault, "read_secret", lambda _: vault.Result(True, value="vault"))
    assert config.secret_value("TEST_CONNECTION") == "vault"


def test_a_missing_connection_has_an_actionable_error_without_a_secret(monkeypatch):
    monkeypatch.delenv("RASAM_MONGO_URI", raising=False)
    monkeypatch.setattr(vault, "read_secret", lambda _: vault.Result(True))
    with pytest.raises(config.ConfigError, match="RASAM_MONGO_URI"):
        config._connection_uri(config.settings.customer)


def test_an_explicit_home_does_not_read_the_project_env(tmp_path):
    shutil.copytree(config.CUSTOMERS_DIR / "demo", tmp_path / "customers" / "demo")
    env = {key: value for key, value in os.environ.items() if not key.startswith("RASAM_")}
    env.update(RASAM_HOME=str(tmp_path), RASAM_CUSTOMER="demo", RASAM_LLM_API_KEY="test",
               RASAM_LLM_BASE_URL="https://example.invalid", RASAM_LLM_MODEL="test",
               RASAM_MONGO_URI="mongodb://test:test@localhost/test", PYTHONUTF8="1")
    script = ("from rasam import config; "
              "assert config.DATA_HOME == __import__('pathlib').Path(__import__('os').environ['RASAM_HOME']); "
              "assert config.settings.csv_dir is None; "
              "assert config.CHROMA_DIR == config.DATA_HOME / 'chroma'; "
              "assert config.settings.mongo_admin_uri is None")
    done = subprocess.run([sys.executable, "-c", script], cwd=config.PROJECT_ROOT,
                          env=env, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr


def test_desktop_default_is_under_appdata(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DESKTOP_MODE", True)
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.delenv("RASAM_HOME", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert config._home_dir() == tmp_path / "Rasam"
