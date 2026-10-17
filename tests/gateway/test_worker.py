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


@pytest.mark.parametrize("known,status,code", [(True, 402, "license_expired"), (False, 401, "license_invalid")])
def test_python_worker_uses_actual_d1_binding_and_returns_safe_license_errors(worker, known, status, code):
    url, key = worker
    response = httpx.post(url + "/v1/chat/completions", timeout=30,
        headers={"Authorization": "Bearer " + (key if known else "unknown-license-test-value")},
        json={"model": "test", "messages": [{"role": "user", "content": "private-test-question"}]})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "private-test-question" not in response.text
