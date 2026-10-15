"""تست API بدون شبکه، دیتابیس یا مدل واقعی."""

from __future__ import annotations

from dataclasses import replace

from bson import ObjectId
from fastapi.testclient import TestClient

from rasam import config
from rasam.core.answer import Answer
from rasam.databases.mongodb.agent import _plain
from rasam import api


client = TestClient(api.app)


def test_health_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_requires_api_key(monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="secret"))
    response = client.post("/ask", json={"question": "دما؟"})
    assert response.status_code == 401


def test_ask_serializes_answer_without_adding_logic(monkeypatch):
    expected = Answer(question="دما؟", rows=[{"avg": 28.6}])
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="secret"))
    monkeypatch.setattr(api, "answer", lambda question: expected)
    response = client.post(
        "/ask", headers={"X-API-Key": "secret"}, json={"question": "دما؟"})
    assert response.status_code == 200
    assert response.json() == {
        "question": "دما؟",
        "source": None,
        "query": None,
        "rows": [{"avg": 28.6}],
        "summary": None,
        "chart": None,
        "repaired": False,
        "message": None,
        "error": None,
    }


def test_ask_can_return_csv(monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="secret"))
    monkeypatch.setattr(api, "answer", lambda question: Answer(
        question=question, rows=[{"avg": 28.6}]))
    response = client.post(
        "/ask", headers={"X-API-Key": "secret"},
        json={"question": "دما؟", "export": "csv"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text == "avg\n28.6\n"


def test_invalid_export_format_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="secret"))
    response = client.post(
        "/ask", headers={"X-API-Key": "secret"},
        json={"question": "دما؟", "export": "pdf"})
    assert response.status_code == 422


def test_a_mongo_id_does_not_break_the_json_response(monkeypatch):
    """این پاسخ قبلاً ۵۰۰ می‌داد: `ObjectId` به JSON تبدیل نمی‌شود.

    ایجنت مونگو حالا ردیف‌ها را ساده می‌کند، پس هر کوئری‌ای که `_id` واقعی
    برمی‌گرداند — یعنی هر کوئری بدون `$group` — از API هم عبور می‌کند.
    """
    identifier = ObjectId()
    rows = [_plain({"_id": identifier, "int_temp": 28.6})]
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="secret"))
    monkeypatch.setattr(api, "answer", lambda question: Answer(
        question=question, rows=rows))
    response = client.post(
        "/ask", headers={"X-API-Key": "secret"}, json={"question": "دما؟"})
    assert response.status_code == 200
    assert response.json()["rows"] == [{"_id": str(identifier), "int_temp": 28.6}]


def test_a_failed_answer_is_not_turned_into_an_empty_file(monkeypatch):
    """قبلاً سوالِ ردشده یک CSV خالی با کد ۲۰۰ می‌گرفت و خطا گم می‌شد."""
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="secret"))
    monkeypatch.setattr(api, "answer", lambda question: Answer(
        question=question, error="کوئری ساخته‌شده پذیرفته نشد."))
    response = client.post(
        "/ask", headers={"X-API-Key": "secret"},
        json={"question": "دما؟", "export": "csv"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"] == "کوئری ساخته‌شده پذیرفته نشد."


def test_export_is_refused_when_the_profile_does_not_have_it(monkeypatch):
    """قابلیت‌های پروفایل باید اثر داشته باشند، نه اینکه تزئینی بمانند."""
    profile = replace(config.settings.customer, capabilities=frozenset({"chart"}))
    monkeypatch.setattr(config, "settings",
                        replace(config.settings, api_key="secret", customer=profile))
    monkeypatch.setattr(api, "answer", lambda question: Answer(
        question=question, rows=[{"avg": 1}]))
    response = client.post(
        "/ask", headers={"X-API-Key": "secret"},
        json={"question": "دما؟", "export": "csv"})
    assert response.status_code == 403


def test_a_non_ascii_configured_key_refuses_instead_of_crashing(monkeypatch):
    """اگر کلید سرور فارسی باشد، `compare_digest` استثنا می‌داد و پاسخ ۵۰۰ می‌شد.

    هدر HTTP خودش نمی‌تواند حرف فارسی حمل کند، پس چنین کلیدی هرگز تطبیق
    نمی‌شود — ولی جوابش باید «کلید غلط» باشد، نه خطای سرور.
    """
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="کلید-قوی"))
    assert client.post("/ask", headers={"X-API-Key": "wrong"},
                       json={"question": "دما؟"}).status_code == 401
