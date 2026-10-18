"""خطای انتقال باید سنجه را ناقص کند؛ متن حساس خطای HTTP وارد گزارش نمی‌شود."""

from dataclasses import asdict
import httpx
import pytest

from rasam.core.answer import Answer
from rasam.desktop.instance import DesktopInstance
from scripts import evaluate, evaluate_http


def test_http_numeric_answer_uses_the_same_grade_and_authentication(monkeypatch):
    def post(url, **kwargs):
        assert url == "http://127.0.0.1:8000/ask"
        assert kwargs["headers"] == {"X-API-Key": "test-key"}
        assert kwargs["json"] == {"question": "q"}
        return httpx.Response(200, json=asdict(Answer(question="q", rows=[{"average": 28.61}])))
    monkeypatch.setattr(evaluate_http.httpx, "post", post)
    answer = evaluate_http.http_answerer("http://127.0.0.1:8000", {"X-API-Key": "test-key"})("q")
    assert evaluate.grade({"value": 28.61}, answer)[0] == "ok"


def test_http_failure_is_incomplete_and_never_echoes_private_server_text(monkeypatch):
    monkeypatch.setattr(evaluate_http.httpx, "post", lambda *a, **kw: httpx.Response(401, text="private-secret"))
    answer = evaluate_http.http_answerer("https://api.example", {})("q")
    assert evaluate.grade({"value": 1}, answer)[0] == "skipped"
    assert "private-secret" not in answer.error


def test_desktop_uses_the_running_instance_without_passing_its_token_in_arguments(tmp_path, monkeypatch):
    instance = DesktopInstance(tmp_path)
    assert instance.acquire()
    try:
        instance.publish(43210, "a" * 40)
        def post(url, **kwargs):
            assert url == "http://127.0.0.1:43210/ask"
            assert kwargs["headers"] == {"X-Rasam-Token": "a" * 40}
            return httpx.Response(200, json=asdict(Answer(question="q", message="جواب")))
        monkeypatch.setattr(evaluate_http.httpx, "post", post)
        monkeypatch.setattr(evaluate_http.httpx, "get", lambda *a, **kw: httpx.Response(200, json={"valid": True}))
        assert evaluate_http.desktop_answerer(tmp_path)("q").message == "جواب"
    finally:
        instance.close()


def test_unavailable_service_stops_evaluation_and_cannot_report_success():
    calls = []
    def unavailable(question):
        calls.append(question)
        return Answer(question=question, error="سرویس در دسترس نیست.")
    questions = [{"question": "q", "expect": {"value": 1}}] * 3
    results = evaluate.run(questions, 0, unavailable)
    assert len(calls) == 1 and evaluate.report(results) != 0


@pytest.mark.parametrize("url", ["http://public.example", "https://user:password@example.com", "https://api.example?key=x"])
def test_evaluation_rejects_credentials_in_urls_and_cleartext_public_transport(url):
    with pytest.raises(ValueError):
        evaluate_http.http_answerer(url, {})
