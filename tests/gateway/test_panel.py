"""ورود و فهرست پنل با نشست واقعی D1؛ هیچ مسیر مدیریتی به لایسنس مشتری اعتماد نمی‌کند."""

import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from admin_panel import app as panel_app, auth
from gateway import admin

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "random-test-password-with-enough-entropy"
ORIGIN = "https://admin.example.test"


class Assets:
    async def fetch(self, url):
        class Asset:
            headers = {"Content-Type": "application/octet-stream"}
            async def text(self):
                return (ROOT / "admin_panel/public" / url.rsplit("/", 1)[-1]).read_text(encoding="utf-8")
            async def bytes(self):
                from urllib.parse import urlsplit
                return (ROOT / "admin_panel/public" / urlsplit(url).path.lstrip("/")).read_bytes()
        return Asset()


class BoundApp:
    def __init__(self, env):
        self.env = env
    async def __call__(self, scope, receive, send):
        scope["env"] = self.env
        await panel_app.app(scope, receive, send)


@pytest.fixture
def panel(d1):
    salt = b"0123456789abcdef"
    hashed = hashlib.pbkdf2_hmac("sha256", PASSWORD.encode(), salt, auth.ITERATIONS).hex()
    env = SimpleNamespace(DB=d1, ASSETS=Assets(), ADMIN_ORIGIN=ORIGIN,
        ADMIN_USERNAME="admin@example.test", ADMIN_PASSWORD_HASH=f"pbkdf2-sha256${auth.ITERATIONS}${salt.hex()}${hashed}")
    asyncio.run(d1.prepare("DELETE FROM admin_login_limits").run())
    client = TestClient(BoundApp(env), base_url=ORIGIN, headers={"Origin": ORIGIN})
    return client, env


def sign_in(client, **values):
    return client.post("/api/login", json={"username": "admin@example.test", "password": PASSWORD, **values})


def test_login_requires_credentials_and_uses_secure_server_side_session(panel):
    client, env = panel
    response = sign_in(client)
    assert response.status_code == 200
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert "__Host-rasam_admin=" in cookie and "Domain=" not in cookie
    current = client.get("/api/me")
    assert current.status_code == 200 and len(current.json()["csrf"]) == 64
    assert PASSWORD not in response.text + current.text
    token = client.cookies.get("__Host-rasam_admin")
    row = asyncio.run(env.DB.prepare("SELECT * FROM admin_sessions WHERE token_hash = ?").bind(auth.digest(token)).first())
    assert token not in str(row) and PASSWORD not in str(row)


@pytest.mark.parametrize("path", ["/api/me", "/api/licenses"])
def test_no_license_or_forged_header_can_read_admin_data(panel, path):
    client, env = panel
    key, _, _, sql = admin.issue("test-customer", "monthly")
    asyncio.run(env.DB.prepare(sql).run())
    response = client.get(path, headers={"Authorization": "Bearer " + key, "CF-Access-Authenticated-User-Email": env.ADMIN_USERNAME})
    assert response.status_code == 401
    assert client.get("/panel", follow_redirects=False).status_code == 303
    assert client.get("/panel.html", follow_redirects=False).status_code == 303
    assert client.get("/panel%2Ehtml", follow_redirects=False).status_code == 303
    assert client.get("/panel/", follow_redirects=False).status_code == 404


def test_invalid_username_and_password_have_same_safe_error(panel):
    client, env = panel
    wrong_password = sign_in(client, password="wrong")
    wrong_username = sign_in(client, username="unknown@example.test")
    assert wrong_password.status_code == wrong_username.status_code == 401
    assert wrong_password.json() == wrong_username.json()
    assert not client.cookies


def test_login_rate_limit_is_atomic_and_returns_retry_after(panel):
    client, env = panel
    for _ in range(5):
        assert sign_in(client, password="wrong").status_code == 401
    response = sign_in(client)
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 300


def test_cross_origin_login_and_logout_are_rejected(panel):
    client, env = panel
    assert client.post("/api/login", headers={"Origin": "https://evil.example"},
        json={"username": env.ADMIN_USERNAME, "password": PASSWORD}).status_code == 403
    assert sign_in(client).status_code == 200
    csrf = client.get("/api/me").json()["csrf"]
    assert client.post("/api/logout", json={}).status_code == 403
    assert client.post("/api/logout", json={}, headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/logout", json={}, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/me").status_code == 401


def test_expiry_and_credential_rotation_invalidate_existing_session(panel):
    client, env = panel
    assert sign_in(client).status_code == 200
    original = env.ADMIN_PASSWORD_HASH
    env.ADMIN_PASSWORD_HASH = original[:-1] + ("0" if original[-1] != "0" else "1")
    assert client.get("/api/me").status_code == 401
    env.ADMIN_PASSWORD_HASH = original
    token = client.cookies.get("__Host-rasam_admin")
    asyncio.run(env.DB.prepare("UPDATE admin_sessions SET expires_at = 1 WHERE token_hash = ?").bind(auth.digest(token)).run())
    assert client.get("/api/me").status_code == 401


def test_listing_filters_real_licenses_without_interpreting_search_as_sql(panel):
    client, env = panel
    prefix = "panel-test-" + uuid4().hex
    key, identifier, _, sql = admin.issue(prefix + " <img src=x onerror=alert(1)>", "monthly", 30)
    asyncio.run(env.DB.prepare(sql).run())
    assert sign_in(client).status_code == 200
    response = client.get("/api/licenses", params={"search": prefix, "status": "active"})
    assert response.status_code == 200
    value = response.json()
    assert value["total"] == 1
    assert value["licenses"][0]["identifier"] == identifier
    assert value["licenses"][0]["used_today"] == 0
    assert key not in response.text
    assert client.get("/api/licenses", params={"search": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/api/licenses", params={"status": "invalid"}).status_code == 400


def test_password_never_appears_in_validation_errors(panel):
    client, env = panel
    response = client.post("/api/login", json={"username": [], "password": PASSWORD})
    assert response.status_code == 401 and PASSWORD not in response.text
    response = client.post("/api/login", content='{"password":"' + PASSWORD + '"}', headers={"Content-Type": "text/plain"})
    assert response.status_code == 400 and PASSWORD not in response.text


def test_cookie_does_not_allow_modifying_server_side_identity(panel):
    client, env = panel
    assert sign_in(client).status_code == 200
    client.cookies.set("__Host-rasam_admin", "forged-session-token-with-enough-length-to-look-valid", domain="admin.example.test", path="/")
    assert client.get("/api/licenses").status_code == 401


def test_static_assets_use_python_response_bytes_and_login_never_submits_password_in_url(panel):
    client, env = panel
    for path in ["/admin.js", "/style.css", "/brand.css", "/mark.svg", "/app-icon.png", "/icons/quota.svg"]:
        assert client.get(path).status_code == 200
    assert 'method="post" action="/api/login"' in client.get("/").text
    assert client.get("/.dev.vars").status_code == 404
    assert client.get("/icons/panel.html").status_code == 404
