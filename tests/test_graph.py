"""تست‌های گراف — بدون شبکه و بدون دیتابیس واقعی.

مدل و دیتابیس جعلی می‌شوند تا هر چهار مسیر ممکن امتحان شود: جواب درست، جمله‌ی
فارسی به‌جای کوئری، ردشدن در گارد، و خطای دیتابیس. مهم‌ترینشان مسیر سوم است:
کوئری ردشده هرگز نباید به گره اجرا برسد.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pymongo.errors import PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graph  # noqa: E402
import llm  # noqa: E402

GOOD = {"collection": "inverter_data",
        "pipeline": [{"$group": {"_id": None, "avg": {"$avg": "$int_temp"}}}]}


class FakeCollection:
    def __init__(self, rows, error=None):
        self.rows, self.error, self.ran = rows, error, []

    def aggregate(self, pipeline, maxTimeMS=None):  # noqa: N803 — امضای pymongo
        if self.error:
            raise self.error
        self.ran.append(pipeline)
        return iter(self.rows)


class FakeDatabase(dict):
    pass


@pytest.fixture
def wired(monkeypatch):
    """مدل و دیتابیس جعلی. تست‌ها فقط چیزی را که لازم دارند عوض می‌کنند."""
    collection = FakeCollection([{"avg": 28.61}])
    monkeypatch.setattr(graph.db, "connect", lambda: FakeDatabase(inverter_data=collection))
    monkeypatch.setattr(graph.db, "describe_schema", lambda _: "SCHEMA")
    monkeypatch.setattr(graph.llm, "ask",
                        lambda _: llm.Result(ok=True, text=json.dumps(GOOD), reason=""))
    return collection


def reply(text: str, monkeypatch):
    monkeypatch.setattr(graph.llm, "ask", lambda _: llm.Result(ok=True, text=text, reason=""))


# --- مسیر سالم --------------------------------------------------------------

def test_a_good_question_returns_rows(wired):
    result = graph.answer("میانگین دمای اینورترها؟")
    assert result.rows == [{"avg": 28.61}]
    assert result.collection == "inverter_data"
    assert result.error is None and result.message is None


def test_the_executed_pipeline_is_the_one_the_guard_returned(wired):
    graph.answer("میانگین دما؟")
    assert wired.ran == [GOOD["pipeline"]]


def test_markdown_fences_do_not_break_parsing(wired, monkeypatch):
    """قاعده‌ی ۶ منعشان کرده، ولی مدل‌ها گاهی اضافه می‌کنند."""
    reply(f"```json\n{json.dumps(GOOD)}\n```", monkeypatch)
    assert graph.answer("میانگین دما؟").rows == [{"avg": 28.61}]


# --- جمله‌ی فارسی به‌جای کوئری ----------------------------------------------

def test_a_plain_sentence_becomes_a_message_not_an_error(wired, monkeypatch):
    """«این داده موجود نیست» جواب معتبر است، نه خطا."""
    reply("اطلاعات آب و هوا در داده‌های موجود نیست.", monkeypatch)
    result = graph.answer("آب و هوای فردا؟")
    assert result.message and result.error is None and result.rows == []


def test_a_message_stops_the_graph_before_the_database(wired, monkeypatch):
    reply("این داده موجود نیست.", monkeypatch)
    graph.answer("آب و هوای فردا؟")
    assert wired.ran == []


# --- ردشدن در گارد ----------------------------------------------------------

@pytest.mark.parametrize("bad", [
    {"collection": "inverter_data", "pipeline": [{"$match": {"$where": "1"}}]},
    {"collection": "inverter_data", "pipeline": [{"$out": "stolen"}]},
    {"collection": "billing", "pipeline": [{"$match": {}}]},
    {"collection": "inverter_data", "pipeline": "not a pipeline"},
])
def test_a_rejected_query_never_reaches_the_database(wired, monkeypatch, bad):
    """مهم‌ترین تست این فایل."""
    reply(json.dumps(bad), monkeypatch)
    result = graph.answer("سوال")
    assert result.error and result.rows == []
    assert wired.ran == []


# --- خطاها ------------------------------------------------------------------

def test_a_model_failure_becomes_an_error(wired, monkeypatch):
    monkeypatch.setattr(graph.llm, "ask",
                        lambda _: llm.Result(ok=False, text=None, reason="کلید پذیرفته نشد."))
    assert "کلید پذیرفته نشد." in graph.answer("سوال").error


def test_a_database_failure_becomes_an_error(monkeypatch, wired):
    broken = FakeCollection([], error=PyMongoError("قطع شد"))
    monkeypatch.setattr(graph.db, "connect", lambda: FakeDatabase(inverter_data=broken))
    assert graph.answer("سوال").error is not None


@pytest.mark.parametrize("question", ["", "   ", "\n"])
def test_an_empty_question_is_refused_without_calling_the_model(wired, question):
    assert graph.answer(question).error is not None


def test_an_unexpected_crash_becomes_an_error_value(wired, monkeypatch):
    """قاعده‌ی امنیتی ۷: خطا مقدار است، نه استثنا — حتی وقتی پیش‌بینی نشده."""
    def explode(_):
        raise RuntimeError("چیزی که فکرش را نکرده بودیم")

    monkeypatch.setattr(graph.llm, "ask", explode)
    result = graph.answer("سوال")
    assert result.error is not None and result.rows == []


# --- تفکیک JSON از جمله -----------------------------------------------------

@pytest.mark.parametrize("text, is_query", [
    ('{"collection": "a", "pipeline": []}', True),
    ("این داده موجود نیست.", False),
    ("[1, 2, 3]", False),
    ("", False),
])
def test_json_means_a_query_attempt_anything_else_is_a_sentence(text, is_query):
    parsed, message = graph._parse(text)
    assert (parsed is not None) is is_query
    assert (message is None) is is_query


# --- خلاصه (قدم ۹) ----------------------------------------------------------

def two_step_model(summary_reply: llm.Result):
    """اولین تماس کوئری می‌سازد، تماس خلاصه جواب دیگری می‌گیرد."""
    def ask(prompt: str) -> llm.Result:
        if prompt.startswith("You summarize"):
            return summary_reply
        return llm.Result(ok=True, text=json.dumps(GOOD), reason="")
    return ask


def test_a_good_answer_carries_a_summary(wired, monkeypatch):
    monkeypatch.setattr(graph.llm, "ask", two_step_model(
        llm.Result(ok=True, text="میانگین دما ۲۸٫۶ درجه است.", reason="")))
    result = graph.answer("میانگین دما؟")
    assert result.summary == "میانگین دما ۲۸٫۶ درجه است."
    assert result.rows == [{"avg": 28.61}]


def test_a_failed_summary_keeps_the_table_and_is_not_an_error(wired, monkeypatch):
    """جدول هنوز ارزش دارد؛ شکست خلاصه نباید کل پاسخ را بگیرد."""
    monkeypatch.setattr(graph.llm, "ask", two_step_model(
        llm.Result(ok=False, text=None, reason="سرویس در دسترس نیست.")))
    result = graph.answer("میانگین دما؟")
    assert result.summary is None
    assert result.error is None
    assert result.rows == [{"avg": 28.61}]


def test_no_summary_is_attempted_when_the_guard_rejects(wired, monkeypatch):
    calls = []

    def ask(prompt):
        calls.append(prompt[:20])
        return llm.Result(ok=True, text=json.dumps(
            {"collection": "inverter_data", "pipeline": [{"$out": "x"}]}), reason="")

    monkeypatch.setattr(graph.llm, "ask", ask)
    graph.answer("سوال")
    assert not any(c.startswith("You summarize") for c in calls)


def test_no_summary_is_attempted_for_a_plain_message(wired, monkeypatch):
    reply("این داده موجود نیست.", monkeypatch)
    assert graph.answer("آب و هوا؟").summary is None
