"""مسیر کامل راهنما و سد دسترسی نوشتن، بدون تماس با مدل."""

import json
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient

from rasam import config, customer, vault, desktop_preferences
from rasam.core import desktop_onboarding
from rasam.databases import registry
from rasam.databases.base import AccessReport
from rasam.databases.connectivity import report
from rasam.desktop.app import create_app


class FakeAgent:
    read_only = True
    def __init__(self, **kwargs):
        pass
    @staticmethod
    def connection_fields():
        return []
    @staticmethod
    def test_connection(*args):
        return report("connected")
    def list_sources(self):
        return ["readings", "billing"]
    def list_fields(self, source):
        return ["value"]
    def check_read_only(self):
        return AccessReport(self.read_only, "read")
    @staticmethod
    def read_only_user_script(database):
        return "READ ONLY SCRIPT"


@pytest.fixture
def wizard(tmp_path, monkeypatch):
    stored = {}
    monkeypatch.setattr(config, "DATA_HOME", tmp_path)
    monkeypatch.setattr(config, "CUSTOMERS_DIR", tmp_path / "customers")
    monkeypatch.setattr(config, "settings", config.settings)
    monkeypatch.setattr(registry, "AGENTS", {"test": FakeAgent})
    monkeypatch.setattr(vault, "read_secret", lambda key: vault.Result(True, value=stored.get(key)))
    monkeypatch.setattr(vault, "write_secret", lambda key, value: (stored.update({key: value}) or vault.Result(True)))
    monkeypatch.setattr(vault, "delete_secret", lambda key: (stored.pop(key, None) or vault.Result(True)))
    app = create_app("token")
    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1), headers={"X-Rasam-Token": "token"})
    result = client.post("/setup/test", json={"db_type": "test", "values": {"database": "demo"},
                                            "advanced_uri": "test://reader:private@server/demo"})
    assert result.json()["ok"]
    return client, app, tmp_path, stored


def test_complete_setup_creates_safe_profile_and_preserves_secret_only_in_vault(wizard):
    client, app, home, stored = wizard
    assert client.get("/setup/sources").json()["sources"] == [
        {"name": "readings", "sensitive": False}, {"name": "billing", "sensitive": True}]
    result = client.post("/setup/profile", json={"name": "trial", "sources": ["readings"]}).json()
    assert result["ok"], result
    profile = customer.load_profile("trial", home / "customers")
    assert profile.allowed_sources == {"readings"} and profile.limits["max_rows"] == 1000
    assert profile.capabilities == customer.KNOWN_CAPABILITIES
    assert config.settings.customer.name == "trial"
    assert desktop_preferences.read_customer(home) == "trial"
    assert app.state.setup.pending is None
    assert set(item["status"] for item in result["checks"]) == {"ok", "warning"}
    assert len(stored) == 1 and "private" in next(iter(stored.values()))
    for path in home.rglob("*"):
        if path.is_file():
            assert "private" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("sources,confirmed", [([], []), (["missing"], []), (["billing"], [])])
def test_empty_forged_or_unconfirmed_sources_are_rejected(wizard, sources, confirmed):
    client, app, home, stored = wizard
    result = client.post("/setup/profile", json={"name": "trial", "sources": sources,
                                               "confirmed_sensitive": confirmed}).json()
    assert not result["ok"] and not (home / "customers" / "trial").exists()


def test_sensitive_selection_requires_and_accepts_explicit_confirmation(wizard):
    client, app, home, stored = wizard
    result = client.post("/setup/profile", json={"name": "trial", "sources": ["billing"],
                                               "confirmed_sensitive": ["billing"]}).json()
    assert result["ok"], result


def test_writer_is_blocked_even_if_client_forges_profile_submission(wizard, monkeypatch):
    client, app, home, stored = wizard
    monkeypatch.setattr(FakeAgent, "read_only", False)
    inspected = client.get("/setup/sources").json()
    assert not inspected["ok"] and inspected["script"] == "READ ONLY SCRIPT"
    result = client.post("/setup/profile", json={"name": "trial", "sources": ["readings"]}).json()
    assert not result["ok"] and not (home / "customers").exists()


def test_path_traversal_and_existing_customer_are_rejected(wizard):
    client, app, home, stored = wizard
    assert not client.post("/setup/profile", json={"name": "../trial", "sources": ["readings"]}).json()["ok"]
    folder = home / "customers" / "trial"
    folder.mkdir(parents=True)
    (folder / "keep.txt").write_text("keep", encoding="utf-8")
    assert not client.post("/setup/profile", json={"name": "trial", "sources": ["readings"]}).json()["ok"]
    assert (folder / "keep.txt").read_text() == "keep"


def test_desktop_restart_reads_saved_customer_without_env(wizard, monkeypatch):
    client, app, home, stored = wizard
    desktop_preferences.write_customer(home, "trial")
    monkeypatch.delenv("RASAM_CUSTOMER", raising=False)
    monkeypatch.setattr(config, "DESKTOP_MODE", True)
    assert config.env_value("CUSTOMER") == "trial"


def test_switching_customer_clears_all_customer_knowledge_caches(tmp_path, monkeypatch):
    from rasam.core import activation, knowledge
    first, second = tmp_path / "first", tmp_path / "second"
    for folder in (first, second):
        folder.mkdir()
        (folder / "documentation.md").write_text(folder.name, encoding="utf-8")
        (folder / "field_notes.yaml").write_text("value: " + folder.name, encoding="utf-8")
        (folder / "examples.yaml").write_text("[]", encoding="utf-8")
    previous = config.settings
    initial = replace(previous, customer=replace(previous.customer, directory=first))
    following = replace(previous, customer=replace(previous.customer, directory=second))
    monkeypatch.setattr(config, "settings", initial)
    knowledge.documentation_text.cache_clear()
    knowledge.field_notes.cache_clear()
    assert knowledge.documentation_text() == "first"
    assert knowledge.field_notes()["value"] == "first"
    monkeypatch.setattr(config, "_load", lambda *args, **kwargs: following)
    activation.activate("second")
    assert knowledge.documentation_text() == "second"
    assert knowledge.field_notes()["value"] == "second"
    knowledge.documentation_text.cache_clear()
    knowledge.field_notes.cache_clear()


@pytest.mark.parametrize("kind", ["mongodb", "mysql"])
def test_read_only_scripts_quote_untrusted_database_names(kind):
    from rasam.databases.mongodb import MongoAgent
    from rasam.databases.mysql import MySQLAgent
    agent = {"mongodb": MongoAgent, "mysql": MySQLAgent}[kind]
    script = agent.read_only_user_script('db`name"; bad')
    assert "rasam_reader" in script
    if kind == "mysql":
        assert '`db``name"; bad`' in script
    else:
        assert 'db`name\\"; bad' in script
