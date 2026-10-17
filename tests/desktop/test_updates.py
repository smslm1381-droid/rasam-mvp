"""خطای بررسی نسخه نباید مانع کار شود؛ پیوند ناسالم هرگز به صفحه نمی‌رسد."""

import httpx
import pytest
from fastapi.testclient import TestClient

from rasam.core import updates
from rasam.desktop.app import create_app


def test_new_release_compares_numbers_and_requires_a_download():
    data = {"version": "1.10.0", "download_url": "https://downloads.example/RasamSetup.exe"}
    assert updates.release_status(data, "1.9.9")["available"]
    assert not updates.release_status(data, "1.10.0")["available"]
    assert not updates.release_status(data, "2.0.0")["available"]
    assert not updates.release_status({**data, "download_url": None}, "1.9.9")["available"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///C:/private", "http://example.com",
                                "https://user:secret@example.com", "https://[", "https://example.com/\n"])
def test_untrusted_release_link_is_never_returned_to_the_ui(url, monkeypatch):
    monkeypatch.setattr(updates.desktop_service, "gateway_url", lambda: "https://gateway.example")
    response = httpx.Response(200, json={"version": "999.0.0", "download_url": url})
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: response)
    assert not updates.check()["available"]


def test_offline_update_check_does_not_break_the_authenticated_desktop(monkeypatch):
    monkeypatch.setattr(updates.desktop_service, "gateway_url", lambda: "https://gateway.example")
    def offline(*args, **kwargs):
        raise httpx.ConnectError("private-network-detail")
    monkeypatch.setattr(updates.httpx, "get", offline)
    client = TestClient(create_app("local-token"), base_url="http://127.0.0.1", client=("127.0.0.1", 1234))
    assert client.get("/updates").status_code == 401
    response = client.get("/updates", headers={"X-Rasam-Token": "local-token"})
    assert response.status_code == 200 and not response.json()["available"]
    assert "private-network-detail" not in response.text


def test_authenticated_desktop_returns_a_new_release(monkeypatch):
    monkeypatch.setattr(updates.desktop_service, "gateway_url", lambda: "https://gateway.example")
    data = {"version": "99.1.0", "download_url": "https://downloads.example/RasamSetup.exe"}
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: httpx.Response(200, json=data))
    client = TestClient(create_app("local-token"), base_url="http://127.0.0.1", client=("127.0.0.1", 1234))
    assert client.get("/updates", headers={"X-Rasam-Token": "local-token"}).json() == {
        **data, "available": True, "current_version": updates.__version__}
