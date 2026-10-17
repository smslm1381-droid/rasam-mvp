"""آزمون خودِ Python Worker برای تفاوت‌های FFI؛ بدون تماس با سرویس مدل."""

import os
import time
from urllib.parse import urlsplit
from uuid import uuid4
import httpx
import pytest
from gateway import admin, d1_cli


def wait_until_ready(url):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url + "/health", timeout=5)
            if response.status_code == 200 and response.json() == {"status": "ok"}:
                return
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.25)
    pytest.fail("Python Worker در زمان مجاز آماده نشد؛ خروجی pywrangler dev را بررسی کنید.")


@pytest.fixture(scope="module")
def worker():
    url = os.getenv("RASAM_GATEWAY_TEST_URL")
    if not url:
        pytest.skip("آزمون Python Worker به pywrangler dev و RASAM_GATEWAY_TEST_URL نیاز دارد.")
    parts = urlsplit(url)
    assert parts.scheme == "http" and parts.hostname == "127.0.0.1" and not parts.username
    wait_until_ready(url.rstrip("/"))
    key, identifier, expires, sql = admin.issue("test-worker-" + uuid4().hex, "monthly", now=1)
    d1_cli.execute(sql)
    try:
        yield url.rstrip("/"), key
    finally:
        d1_cli.execute("DELETE FROM licenses WHERE token_hash = '" + identifier + "';")


def test_python_worker_health(worker):
    url, key = worker
    assert httpx.get(url + "/health", timeout=30).json() == {"status": "ok"}


def test_python_worker_license_status_reads_d1_without_spending_quota(worker):
    """وضعیت لایسنس باید از خود Worker بیاید و سهمیهٔ پرسش را مصرف نکند."""
    url, key = worker
    headers = {"Authorization": "Bearer " + key}
    response = httpx.get(url + "/license/status", headers=headers, timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False and data["code"] == "license_expired"
    assert data["days_remaining"] == 0 and data["used_today"] == 0
    assert data["model"] and key not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert httpx.get(url + "/license/status", headers=headers, timeout=30).json() == data
    unknown = httpx.get(url + "/license/status", timeout=30,
                       headers={"Authorization": "Bearer unknown-license-test-value"})
    assert unknown.status_code == 401
    assert unknown.json()["error"]["code"] == "license_invalid"


def test_python_worker_status_matches_desktop_after_expiry_and_renewal(worker):
    """قرارداد واقعی سرور و رومیزی باید پس از تمدید هم سازگار بماند."""
    from rasam.core.licensing import fetch_status

    url, _ = worker
    key, identifier, _, sql = admin.issue("test-renew-" + uuid4().hex, "monthly", now=1)
    d1_cli.execute(sql)
    try:
        assert fetch_status(url, key)["code"] == "license_expired"
        d1_cli.execute(admin.change(identifier, days=6))
        current = fetch_status(url, key)
        assert current["valid"] and current["days_remaining"] == 6
        assert current["used_today"] == 0
        d1_cli.execute(admin.change(identifier))
        assert fetch_status(url, key)["code"] == "license_revoked"
        d1_cli.execute(admin.change(identifier, days=30))
        renewed = fetch_status(url, key)
        assert renewed["valid"] and renewed["days_remaining"] == 36
        assert renewed["used_today"] == 0
    finally:
        d1_cli.execute("DELETE FROM licenses WHERE token_hash = '" + identifier + "';")


@pytest.mark.parametrize("known,status,code", [(True, 402, "license_expired"), (False, 401, "license_invalid")])
def test_python_worker_uses_actual_d1_binding_and_returns_safe_license_errors(worker, known, status, code):
    url, key = worker
    response = httpx.post(url + "/v1/chat/completions", timeout=30,
        headers={"Authorization": "Bearer " + (key if known else "unknown-license-test-value")},
        json={"model": "test", "messages": [{"role": "user", "content": "private-test-question"}]})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "private-test-question" not in response.text
