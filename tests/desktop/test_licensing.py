"""فعال‌سازی، تمدید و انقضا بدون پاک‌کردن داده یا افشای کلید."""

from dataclasses import replace
import json
import time
import httpx
import pytest
from fastapi.testclient import TestClient

from rasam import config, vault, desktop_service
from rasam.core import licensing
from rasam.desktop.app import create_app

KEY = "rasam_test_license_for_activation_1234567890"


def status(valid=True, days=30):
    return {"valid": valid, "code": None if valid else "license_expired", "customer": "مشتری آزمایشی",
            "plan": "monthly", "expires_at": int(time.time()) + days * 86400,
            "days_remaining": days, "daily_limit": 20, "used_today": 2,
            "model": "server-model", "support_url": "https://example.com/support"}


@pytest.fixture
def licensed(tmp_path, monkeypatch):
    stored = {}
    state = {"body": status(), "status": 200, "calls": 0}
    monkeypatch.setattr(config, "DESKTOP_MODE", True)
    monkeypatch.setattr(config, "settings", config.settings)
    monkeypatch.setenv("RASAM_GATEWAY_URL", "http://127.0.0.1:8787")
    monkeypatch.setattr(vault, "read_secret", lambda name: vault.Result(True, value=stored.get(name)))
    monkeypatch.setattr(vault, "write_secret", lambda name, value: (stored.update({name: value}) or vault.Result(True)))
    def get(url, **kwargs):
        state["calls"] += 1
        assert url == "http://127.0.0.1:8787/license/status"
        assert kwargs["follow_redirects"] is False
        return httpx.Response(state["status"], json=state["body"])
    monkeypatch.setattr(licensing.httpx, "get", get)
    manager = licensing.LicenseManager("TEST_LICENSE")
    app = create_app("token", license_manager=manager)
    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1),
                        headers={"X-Rasam-Token": "token"})
    return client, manager, stored, state


def test_first_launch_requires_license_before_setup_and_cannot_use_direct_provider_key(licensed):
    client, manager, stored, state = licensed
    result = client.get("/license/status").json()
    assert result["required"] and not result["valid"] and result["code"] == "missing"
    assert state["calls"] == 0
    assert config.settings.llm_api_key == "" and config.settings.llm_model == ""
    assert config.settings.llm_base_url == "http://127.0.0.1:8787/v1"


def test_valid_activation_saves_only_in_vault_and_returns_public_metadata(licensed):
    client, manager, stored, state = licensed
    response = client.post("/license/activate", json={"key": KEY})
    result = response.json()
    assert result["ok"] and result["valid"] and result["days_remaining"] == 30
    assert stored == {"TEST_LICENSE": KEY}
    assert KEY not in response.text and "server-model" not in response.text
    assert config.settings.llm_api_key == KEY and config.settings.llm_model == "server-model"
    assert client.get("/license/status").json()["customer"] == "مشتری آزمایشی"


def test_invalid_key_does_not_replace_the_working_license_or_echo_server_text(licensed):
    client, manager, stored, state = licensed
    assert manager.activate(KEY)["ok"]
    state.update(status=401, body={"error": {"code": "license_invalid", "message": "private-server-text"}})
    response = client.post("/license/activate", json={"key": "wrong-license-value-1234567890"})
    assert not response.json()["ok"]
    assert "private-server-text" not in response.text and stored["TEST_LICENSE"] == KEY


def test_expired_license_preserves_files_and_renewal_works_without_reinstall(licensed, tmp_path, monkeypatch):
    client, manager, stored, state = licensed
    folder = tmp_path / "customer"
    folder.mkdir()
    path = folder / "documentation.md"
    path.write_text("customer knowledge", encoding="utf-8")
    monkeypatch.setattr(config, "settings", replace(config.settings,
        customer=replace(config.settings.customer, directory=folder)))
    stored["TEST_LICENSE"] = KEY
    state["body"] = status(False, 0)
    assert client.get("/license/status").json()["code"] == "license_expired"
    assert path.read_text() == "customer knowledge" and stored["TEST_LICENSE"] == KEY
    state["body"] = status(True, 365)
    result = client.get("/license/status").json()
    assert result["valid"] and result["days_remaining"] == 365
    assert path.read_text() == "customer knowledge" and stored["TEST_LICENSE"] == KEY


def test_activation_before_customer_profile_still_configures_model_after_profile_creation(licensed, monkeypatch):
    client, manager, stored, state = licensed
    original = config.settings
    monkeypatch.setattr(config, "settings", None)
    assert manager.activate(KEY)["ok"]
    config.settings = original
    manager.configure_runtime()
    assert config.settings.llm_api_key == KEY and config.settings.llm_model == "server-model"


def test_network_error_never_echoes_credentials_and_keeps_license(licensed, monkeypatch):
    client, manager, stored, state = licensed
    stored["TEST_LICENSE"] = KEY
    def fail(*args, **kwargs):
        raise httpx.ConnectError("secret=" + KEY)
    monkeypatch.setattr(licensing.httpx, "get", fail)
    response = client.get("/license/status")
    assert response.json()["code"] == "network" and KEY not in response.text
    assert stored["TEST_LICENSE"] == KEY


def test_license_routes_are_token_protected_and_invalid_input_is_not_echoed(licensed):
    client, manager, stored, state = licensed
    assert client.get("/license/status", headers={"X-Rasam-Token": ""}).status_code == 401
    response = client.post("/license/activate", json={"key": "private-short"})
    assert response.status_code == 422 and "private-short" not in response.text
    assert state["calls"] == 0 and not stored


def test_api_and_development_mode_do_not_require_license_or_read_its_vault(monkeypatch):
    monkeypatch.setattr(config, "DESKTOP_MODE", False)
    before = config.settings
    def fail(*args):
        raise AssertionError("license vault must not be read")
    monkeypatch.setattr(vault, "read_secret", fail)
    manager = licensing.LicenseManager()
    manager.configure_runtime()
    assert manager.refresh() == {"required": False, "valid": True}
    assert config.settings is before


@pytest.mark.parametrize("url", ["http://external.example.com", "javascript:bad", "https://u:p@example.com", "https://example.com?key=x"])
def test_service_configuration_rejects_insecure_or_credential_urls(monkeypatch, url):
    monkeypatch.setenv("RASAM_GATEWAY_URL", url)
    assert desktop_service.gateway_url() is None


def test_bundled_service_configuration_contains_only_a_public_url(tmp_path, monkeypatch):
    monkeypatch.delenv("RASAM_GATEWAY_URL", raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (tmp_path / "desktop-service.json").write_text(json.dumps({"gateway_url": "https://service.example.com"}), encoding="utf-8")
    assert desktop_service.gateway_url() == "https://service.example.com"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://u:p@example.com", "http://example.com"])
def test_untrusted_support_link_is_not_exposed(url):
    data = {**status(), "support_url": url}
    assert licensing.clean_status(data)["support_url"] == ""
