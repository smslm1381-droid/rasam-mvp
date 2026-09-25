"""تست نمودار امن، بدون شبکه و دیتابیس واقعی."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import charting  # noqa: E402
import db  # noqa: E402
import graph  # noqa: E402
import llm  # noqa: E402


ROWS = [{"timestamp": 1_700_000_000, "avg": 20.5},
        {"timestamp": 1_700_003_600, "avg": 21.5}]


def test_wants_chart_requires_an_explicit_chart_word():
    assert charting.wants_chart("نمودار دمای اینورترها")
    assert charting.wants_chart("دمای اینورترها چقدر است؟") is False


def test_local_check_rejects_empty_single_and_non_numeric_results():
    assert charting.local_check([])[0] is False
    assert charting.local_check([{"state": "Run"}])[0] is False
    assert charting.local_check([{"value": 1}])[0] is False


def test_model_columns_are_filtered_and_chart_type_is_safe():
    reply = json.dumps({
        "feasible": True,
        "chart_type": "made-up",
        "x": "invented",
        "y": ["avg", "secret", "timestamp"],
        "title": "نمودار دما",
    })
    assert charting.parse_and_validate(reply, ROWS) == {
        "chart_type": "bar",
        "x": None,
        "y": ["avg", "timestamp"],
        "title": "نمودار دما",
    }


def test_single_value_result_never_calls_the_chart_model(monkeypatch):
    calls = []
    original = graph.llm.ask

    def ask(prompt):
        calls.append(prompt)
        if prompt.startswith("You summarize"):
            return llm.Result(ok=True, text="خلاصه.", reason="")
        return original(prompt)

    monkeypatch.setattr(graph.llm, "ask", ask)
    monkeypatch.setattr(db, "connect", lambda: {
        "inverter_data": _Collection([{"avg": 28.6}]),
    })
    monkeypatch.setattr(db, "describe_schema", lambda _: "SCHEMA")
    monkeypatch.setattr(graph.llm, "ask", lambda prompt: _reply_for(prompt, calls))
    result = graph.answer("نمودار میانگین دما")
    assert result.chart is None
    assert not any(prompt.startswith("You specify a chart") for prompt in calls)


def test_a_question_without_chart_request_never_reaches_chart(monkeypatch):
    calls = []
    monkeypatch.setattr(db, "connect", lambda: {
        "inverter_data": _Collection(ROWS),
    })
    monkeypatch.setattr(db, "describe_schema", lambda _: "SCHEMA")

    def ask(prompt):
        calls.append(prompt)
        if prompt.startswith("You summarize"):
            return llm.Result(ok=True, text="خلاصه.", reason="")
        return llm.Result(ok=True, text=json.dumps({
            "collection": "inverter_data",
            "pipeline": [],
        }), reason="")

    monkeypatch.setattr(graph.llm, "ask", ask)
    result = graph.answer("میانگین دما را نشان بده")
    assert result.chart is None
    assert not any(prompt.startswith("You specify a chart") for prompt in calls)


class _Collection:
    def __init__(self, rows):
        self.rows = rows

    def aggregate(self, pipeline, maxTimeMS=None):  # noqa: N803
        return iter(self.rows)


def _reply_for(prompt, calls):
    calls.append(prompt)
    if prompt.startswith("You summarize"):
        return llm.Result(ok=True, text="خلاصه.", reason="")
    return llm.Result(ok=True, text=json.dumps({
        "collection": "inverter_data",
        "pipeline": [],
    }), reason="")