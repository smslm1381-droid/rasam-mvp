"""احراز حساب محلی باید همهٔ مسیرهای داده را ببندد، نه فقط صفحهٔ ورود را."""

import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from rasam.desktop.accounts import LocalAccount
from rasam.desktop.app import create_app

CREDS = {"username": "local-user", "password": "test-password-123"}


@pytest.fixture
def local(tmp_path):
    account = LocalAccount(tmp_path / "account.sqlite3")
    state = {"valid": False}
    manager = SimpleNamespace(configure_runtime=lambda: None,
        refresh=lambda: {"required": True, "valid": state["valid"]})
    app = create_app("token", license_manager=manager, account=account)
    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1),
                        headers={"X-Rasam-Token": "token"})
    return client, account, state


def test_registration_requires_a_valid_license(local):
    client, account, state = local
    assert client.post("/auth/register", json=CREDS).status_code == 403
    assert not account.state()["registered"]
    state["valid"] = True
    response = client.post("/auth/register", json=CREDS)
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/auth/status").json()["authenticated"]
    assert CREDS["password"].encode() not in account.path.read_bytes()


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/status", None), ("GET", "/chats", None),
    ("GET", "/setup/databases", None), ("GET", "/export/anything/csv", None),
    ("POST", "/ask", {"question": "سلام"}),
    ("POST", "/profile/save", {}), ("POST", "/teaching", {}),
])
def test_all_data_routes_require_login_even_with_launch_token(local, method, path, body):
    client, account, state = local
    assert client.request(method, path, json=body).status_code == 401


def test_logout_blocks_old_cookie_and_login_does_not_require_license_entry(local):
    client, account, state = local
    state["valid"] = True
    client.post("/auth/register", json=CREDS)
    cookie = client.cookies.get("rasam_local_account")
    assert client.get("/status").status_code == 200
    client.post("/auth/logout")
    assert client.get("/status").status_code == 401
    client.cookies.set("rasam_local_account", cookie)
    assert client.get("/status").status_code == 401
    client.cookies.clear()
    state["valid"] = False
    assert client.post("/auth/login", json=CREDS).status_code == 200
    assert client.get("/auth/status").json()["authenticated"]


def test_account_survives_restart_but_session_does_not(local):
    client, account, state = local
    state["valid"] = True
    client.post("/auth/register", json=CREDS)
    token = client.cookies.get("rasam_local_account")
    restarted = LocalAccount(account.path)
    assert restarted.state()["registered"]
    assert not restarted.authenticated(token)
    assert restarted.login(**CREDS).ok
    assert not restarted.register("another", "another-password").ok


def test_wrong_credentials_are_limited_across_restart(local):
    client, account, state = local
    account.register(**CREDS)
    for _ in range(5):
        assert not account.login("wrong-user", CREDS["password"]).ok
    restarted = LocalAccount(account.path)
    assert "پنج دقیقه" in restarted.login(**CREDS).reason
    with sqlite3.connect(account.path) as db:
        db.execute("UPDATE account SET retry_at=1")
    assert restarted.login(**CREDS).ok


def test_existing_account_cannot_be_overwritten_or_license_changed_without_login(local):
    client, account, state = local
    account.register(**CREDS)
    state["valid"] = True
    assert client.post("/auth/register", json=CREDS).status_code == 401
    assert client.post("/license/activate", json={"key": "x" * 30}).status_code == 401
    assert client.get("/license/status").status_code == 401
    assert client.get("/auth/status").json() == {"required": True, "registered": True, "authenticated": False}


def test_cross_origin_and_missing_launch_token_cannot_login(local):
    client, account, state = local
    account.register(**CREDS)
    assert client.post("/auth/login", json=CREDS, headers={"Origin": "https://evil.example"}).status_code == 403
    client.headers.clear()
    assert client.post("/auth/login", json=CREDS).status_code == 401


def test_storage_error_fails_closed(tmp_path):
    path = tmp_path / "directory"
    path.mkdir()
    account = LocalAccount(path)
    assert account.state()["error"]
    assert not account.login(**CREDS).ok
    assert not account.register(**CREDS).ok
