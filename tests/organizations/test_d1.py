"""همان پل Worker و RemoteStore روی Miniflare واقعی؛ این آزمون استقرار ابری نیست."""

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess

from cryptography.fernet import Fernet
import httpx
import pytest

from organization_portal import invitations, organizations, usage
from organization_portal.auth import Accounts
from organization_portal.chats import Chats
from organization_portal.connections import Connections
from organization_portal.store import RemoteStore
from tests.organizations.conftest import FakeEngine

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def remote_store():
    node = shutil.which("node")
    if not node or not (ROOT / "gateway/node_modules/miniflare").is_dir():
        pytest.skip("Node و ابزارهای محلی gateway برای شبیه‌ساز D1 لازم‌اند.")
    key = secrets.token_urlsafe(48)
    process = subprocess.Popen([node, str(Path(__file__).with_name("d1_server.mjs"))], cwd=ROOT,
        env={**os.environ, "RASAM_TEST_STORAGE_KEY": key}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8")
    try:
        line = process.stdout.readline()
        assert line, "شبیه‌ساز D1 شروع نشد."
        port = json.loads(line)["port"]
        yield RemoteStore(f"http://127.0.0.1:{port}", key)
    finally:
        process.terminate()
        process.wait(timeout=20)


def test_remote_d1_supports_invites_private_chats_and_atomic_quota(remote_store):
    store = remote_store
    accounts = Accounts(store)
    password = "test-only-d1-password-123"
    identity = accounts.create("platform@example.invalid", "مدیر تست", password, True)
    platform = accounts.current(accounts.login("platform@example.invalid", password, "test"))
    org = organizations.create(store, platform, "سازمان تست D1", "manager@example.invalid", ["127.0.0.1"], 2)
    invitations.accept(store, org["invitation"]["token"], "مدیر سازمان", password, None)
    manager = accounts.current(accounts.login("manager@example.invalid", password, "test-two"))
    engine = FakeEngine()
    connection = Connections(store, Fernet.generate_key().decode(), engine, local=True)
    data = {"db_type": "mysql", "values": {"host": "127.0.0.1", "username": "reader",
            "password": "test-db-password", "database": "data"}, "sources": ["readings"]}
    assert connection.save(manager, org["id"], data)["ok"]
    chats = Chats(store, connection)
    chat = chats.create(manager, org["id"])["id"]
    request = secrets.token_hex(16)
    assert not chats.ask(manager, org["id"], chat, request, "پرسش تست D1")["reused"]
    assert chats.ask(manager, org["id"], chat, request, "پرسش تست D1")["reused"]
    assert chats.read(manager, org["id"], chat)["turns"][0]["answer"]["message"]
    assert usage.summary(store, org["id"], manager["id"])["member"] == {"used": 1, "reserved": 0}


def test_storage_bridge_rejects_browser_and_wrong_service_secret(remote_store):
    response = httpx.post(remote_store.url, json={"statements": [{"sql": "SELECT * FROM users", "params": []}]},
                          headers={"Authorization": "Bearer " + "wrong" * 10}, trust_env=False)
    assert response.status_code == 403
    assert "password_hash" not in response.text
