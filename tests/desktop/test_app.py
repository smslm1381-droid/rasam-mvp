"""احراز دسترسی محلی و یکسان‌بودن Answer و خروجی فایل، بدون تماس با مدل."""

from __future__ import annotations

import io
from dataclasses import asdict, replace

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from rasam import config
from rasam.core.answer import Answer
from rasam.desktop.app import create_app

TOKEN = "test-session-token"
HEADERS = {"X-Rasam-Token": TOKEN}


def client_for(answerer=None, remote=False):
    app = create_app(TOKEN, answerer)
    return TestClient(app, base_url="http://127.0.0.1", client=("192.168.1.9" if remote else "127.0.0.1", 1234))


def test_without_token_no_document_or_data_is_accessible():
    client = client_for()
    assert client.get("/").status_code == 401
    assert client.get("/status").status_code == 401
    assert client.post("/ask", json={"question": "q"}).status_code == 401


def test_query_token_is_accepted_only_for_the_initial_document():
    client = client_for()
    response = client.get("/?token=" + TOKEN)
    assert response.status_code == 200 and 'dir="rtl"' in response.text
    assert client.get("/status?token=" + TOKEN).status_code == 401


def test_each_launch_has_a_new_random_token():
    first, second = create_app(), create_app()
    assert len(first.state.token) >= 32
    assert first.state.token != second.state.token


def test_refresh_uses_a_session_cookie_but_api_still_requires_the_header():
    client = client_for()
    response = client.get("/?token=" + TOKEN)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert client.get("/").status_code == 200
    assert client.get("/status").status_code == 401


def test_even_a_valid_token_cannot_be_used_from_the_network():
    client = client_for(remote=True)
    assert client.get("/status", headers={**HEADERS, "X-Forwarded-For": "127.0.0.1"}).status_code == 403


@pytest.mark.parametrize("headers", [{"Origin": "https://example.org"},
    {"Host": "example.org"}, {"Sec-Fetch-Site": "cross-site"}])
def test_other_websites_and_rebinding_are_rejected(headers):
    assert client_for().get("/status", headers={**HEADERS, **headers}).status_code == 403


def test_security_headers_prevent_framing_and_token_referrers():
    response = client_for().get("/?token=" + TOKEN)
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert "script-src 'self'" in response.headers["content-security-policy"]


def test_answer_is_serialized_and_downloads_reuse_its_exact_rows():
    calls = []
    answer = Answer(question="دما؟", rows=[{"دما": 28.6}], summary="پاسخ فارسی")
    client = client_for(lambda question: calls.append(question) or answer)
    response = client.post("/ask", headers=HEADERS, json={"question": "دما؟"})
    assert response.json() == asdict(answer)
    identity = response.headers["X-Answer-ID"]
    csv = client.get(f"/export/{identity}/csv", headers=HEADERS)
    excel = client.get(f"/export/{identity}/excel", headers=HEADERS)
    assert csv.content.startswith(b"\xef\xbb\xbf")
    assert csv.content.decode("utf-8-sig").splitlines() == ["دما", "28.6"]
    assert list(load_workbook(io.BytesIO(excel.content)).active.values) == [("دما",), (28.6,)]
    assert calls == ["دما؟"]


def test_old_answer_cannot_silently_export_a_new_answers_rows():
    client = client_for(lambda question: Answer(question=question, rows=[{"n": 1}]))
    identity = client.post("/ask", headers=HEADERS, json={"question": "first"}).headers["X-Answer-ID"]
    client.post("/ask", headers=HEADERS, json={"question": "second"})
    assert client.get(f"/export/{identity}/csv", headers=HEADERS).status_code == 404


def test_disabled_exports_are_rejected_on_the_server(monkeypatch):
    profile = replace(config.settings.customer, capabilities=frozenset())
    monkeypatch.setattr(config, "settings", replace(config.settings, customer=profile))
    client = client_for(lambda question: Answer(question=question, rows=[{"n": 1}]))
    identity = client.post("/ask", headers=HEADERS, json={"question": "q"}).headers["X-Answer-ID"]
    assert client.get(f"/export/{identity}/csv", headers=HEADERS).status_code == 403


def test_unconfigured_install_can_show_the_page_and_explain_setup(monkeypatch):
    monkeypatch.setattr(config, "settings", None)
    client = client_for()
    assert client.get("/?token=" + TOKEN).status_code == 200
    assert client.get("/status", headers=HEADERS).json()["configured"] is False
    answer = client.post("/ask", headers=HEADERS, json={"question": "q"}).json()
    assert "اتصال" in answer["error"]


def test_invalid_input_does_not_echo_a_password_or_raw_payload():
    response = client_for().post("/ask", headers=HEADERS, json={"question": {"password": "SECRET"}})
    assert response.status_code == 422
    assert "SECRET" not in response.text


def test_the_page_assets_work_without_an_external_connection():
    client = client_for()
    for name in ("app.js", "style.css", "plotly.min.js", "Vazirmatn-Regular.woff2"):
        response = client.get("/static/" + name)
        assert response.status_code == 200 and response.content


def test_unexpected_errors_do_not_escape_or_expose_credentials():
    def broken(question):
        raise RuntimeError("password=SECRET")
    response = client_for(broken).post("/ask", headers=HEADERS, json={"question": "q"})
    assert response.status_code == 200 and response.json()["error"]
    assert "SECRET" not in response.text
