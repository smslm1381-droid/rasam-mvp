"""تست API بدون شبکه، دیتابیس یا مدل واقعی."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import graph  # noqa: E402
from api import main  # noqa: E402


client = TestClient(main.app)


def test_health_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_requires_api_key(monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="secret"))
    response = client.post("/ask", json={"question": "دما؟"})
    assert response.status_code == 401


def test_ask_serializes_answer_without_adding_logic(monkeypatch):
    expected = graph.Answer(question="دما؟", rows=[{"avg": 28.6}])
    monkeypatch.setattr(config, "settings", replace(config.settings, api_key="secret"))
    monkeypatch.setattr(main, "answer", lambda question: expected)
    response = client.post(
        "/ask", headers={"X-API-Key": "secret"}, json={"question": "دما؟"})
    assert response.status_code == 200
    assert response.json() == {
        "question": "دما؟",
        "collection": None,
        "pipeline": None,
        "rows": [{"avg": 28.6}],
        "summary": None,
        "chart": None,
        "repaired": False,
        "message": None,
        "error": None,
    }