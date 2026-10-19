"""مسیر HTTP با دو مرورگر مستقل، CSRF و ورودی حساس بررسی می‌شود."""

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest

from organization_portal.app import create_app
from organization_portal.settings import Settings


@pytest.fixture
def portal(workspace, tmp_path):
    settings = Settings(tmp_path, "http://127.0.0.1:8795", workspace["key"], local=True)
    app = create_app(settings, store=workspace["store"], engine=workspace["engine"])
    accounts = app.state.accounts
    identity = accounts.create("login@example.invalid", "عضو آزمایشی", "test-only-password-123")
    workspace["store"].query("INSERT INTO memberships(id,org_id,user_id,role,daily_limit,allowed_sources) VALUES (?,?,?,'member',5,'[\"readings\"]')",
                             "login", "one", identity)
    return app, settings


def logged(app, settings):
    client = TestClient(app, base_url=settings.origin)
    headers = {"Origin": settings.origin}
    response = client.post("/api/auth/login", headers=headers,
                           json={"email": "login@example.invalid", "password": "test-only-password-123"})
    assert response.status_code == 200
    state = client.get("/api/auth/status").json()
    return client, {**headers, "X-CSRF-Token": state["csrf"]}


def test_two_browsers_share_central_chats_after_login(portal):
    app, settings = portal
    first, headers = logged(app, settings)
    second, _ = logged(app, settings)
    chat = first.post("/api/organizations/one/chats", headers=headers).json()
    assert second.get("/api/organizations/one/chats").json()[0]["id"] == chat["id"]


def test_unauthenticated_or_cross_origin_requests_cannot_access_data(portal):
    app, settings = portal
    client = TestClient(app, base_url=settings.origin)
    assert client.get("/api/organizations/one/chats").status_code == 401
    assert client.post("/api/auth/login", headers={"Origin": "https://other.invalid"},
        json={"email": "login@example.invalid", "password": "test-only-password-123"}).status_code == 403


def test_session_needs_csrf_and_cookie_is_httponly(portal):
    app, settings = portal
    client, headers = logged(app, settings)
    assert client.post("/api/organizations/one/chats", headers={"Origin": settings.origin}).status_code == 403
    assert client.post("/api/organizations/one/chats", headers=headers).status_code == 200
    assert any(cookie.has_nonstandard_attr("HttpOnly") for cookie in client.cookies.jar)


def test_invalid_input_does_not_echo_password_or_raw_validation(portal):
    app, settings = portal
    client = TestClient(app, base_url=settings.origin)
    secret = "PRIVATE_PASSWORD_" * 20
    response = client.post("/api/auth/login", headers={"Origin": settings.origin},
                           json={"email": "x", "password": secret})
    assert response.status_code == 400 and secret not in response.text
    assert "input" not in response.text


def test_hosted_service_requires_worker_secret_and_https(tmp_path, workspace):
    settings = Settings(tmp_path, "https://workspace.example.invalid", Fernet.generate_key().decode(),
                        backend_key="test-backend-" * 5, storage_url="https://workspace.example.invalid",
                        storage_key="test-storage-" * 5)
    app = create_app(settings, store=workspace["store"], engine=workspace["engine"])
    client = TestClient(app, base_url=settings.origin)
    assert client.get("/health").status_code == 200
    assert client.get("/api/auth/status").status_code == 403
    response = client.get("/api/auth/status", headers={"X-Rasam-Proxy-Key": settings.backend_key})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "script-src 'self'" in response.headers['Content-Security-Policy']


def test_nested_routes_have_single_api_prefix_and_check_authorization(portal):
    app, settings = portal
    client, headers = logged(app, settings)
    assert client.get("/api/organizations/one/usage").status_code == 200
    assert client.get("/api/organizations/one/connection").status_code == 403
    assert client.get("/api/invitations/not-a-real-token").status_code == 404
    response = client.post("/api/auth/password", headers=headers,
                           json={"old": "incorrect-test-password", "new": "new-test-password-123"})
    assert response.status_code == 403
    assert not any(getattr(route, 'path', '').startswith('/api/api/') for route in app.routes)
