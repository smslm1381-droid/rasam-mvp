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


# --- خودترمیمی (قدم ۱۰) ----------------------------------------------------

BAD_STAGE = {"collection": "inverter_data", "pipeline": [{"$facet": {"a": []}}]}
STILL_BAD = {"collection": "inverter_data", "pipeline": [{"$out": "stolen"}]}


def scripted(monkeypatch, *replies: str):
    """مدلی که هر بار جواب بعدی فهرست را می‌دهد؛ خلاصه همیشه ثابت است."""
    queue = list(replies)
    seen: list[str] = []

    def ask(prompt: str) -> llm.Result:
        seen.append(prompt)
        if prompt.startswith("You summarize"):
            return llm.Result(ok=True, text="خلاصه.", reason="")
        text = queue.pop(0) if queue else queue_last
        return llm.Result(ok=True, text=text, reason="")

    queue_last = replies[-1] if replies else "{}"
    monkeypatch.setattr(graph.llm, "ask", ask)
    return seen


def test_a_rejected_query_is_repaired_and_then_succeeds(wired, monkeypatch):
    """معیار پذیرش قدم ۱۰."""
    scripted(monkeypatch, json.dumps(BAD_STAGE), json.dumps(GOOD))
    result = graph.answer("سوال")
    assert result.repaired is True
    assert result.error is None
    assert result.rows == [{"avg": 28.61}]


def test_the_repaired_query_is_the_one_that_runs(wired, monkeypatch):
    scripted(monkeypatch, json.dumps(BAD_STAGE), json.dumps(GOOD))
    graph.answer("سوال")
    assert wired.ran == [GOOD["pipeline"]]


def test_the_repair_prompt_carries_the_failure_and_the_reason(wired, monkeypatch):
    seen = scripted(monkeypatch, json.dumps(BAD_STAGE), json.dumps(GOOD))
    graph.answer("سوال")
    repair_prompt = next(p for p in seen if "===Your previous attempt failed" in p)
    assert "$facet" in repair_prompt
    assert "مرحله" in repair_prompt  # دلیل ردشدن، از خودِ گارد


def test_a_repaired_query_still_has_to_pass_the_guard(wired, monkeypatch):
    """مهم‌ترین تست این بخش: ترمیم نباید راه دور زدن گارد باشد."""
    scripted(monkeypatch, json.dumps(BAD_STAGE), json.dumps(STILL_BAD))
    result = graph.answer("سوال")
    assert result.error is not None
    assert wired.ran == []


def test_repair_is_attempted_only_once(wired, monkeypatch):
    seen = scripted(monkeypatch, json.dumps(BAD_STAGE), json.dumps(STILL_BAD))
    graph.answer("سوال")
    assert sum("===Your previous attempt failed" in p for p in seen) == 1


def test_a_good_query_is_never_repaired(wired, monkeypatch):
    seen = scripted(monkeypatch, json.dumps(GOOD))
    result = graph.answer("سوال")
    assert result.repaired is False
    assert not any("===Your previous attempt failed" in p for p in seen)


def test_a_failed_execution_is_also_repaired(monkeypatch, wired):
    """نه فقط ردشدن در گارد — خطای خودِ دیتابیس هم شانس دوم دارد."""
    broken = FakeCollection([], error=PyMongoError("unknown operator"))
    monkeypatch.setattr(graph.db, "connect", lambda: FakeDatabase(inverter_data=broken))
    seen = scripted(monkeypatch, json.dumps(GOOD), json.dumps(GOOD))
    graph.answer("سوال")
    assert any("===Your previous attempt failed" in p for p in seen)


def test_a_repair_that_decides_the_data_is_missing_becomes_a_message(wired, monkeypatch):
    scripted(monkeypatch, json.dumps(BAD_STAGE), "این داده در دیتابیس نیست.")
    result = graph.answer("سوال")
    assert result.message == "این داده در دیتابیس نیست."
    assert result.error is None


def test_a_message_is_never_repaired(wired, monkeypatch):
    seen = scripted(monkeypatch, "این داده موجود نیست.")
    graph.answer("سوال")
    assert not any("===Your previous attempt failed" in p for p in seen)


# --- سوال بیش از حد بلند -----------------------------------------------------

def test_an_over_long_question_is_refused_not_truncated(wired, monkeypatch):
    """کاربر باید بفهمد چرا جواب نگرفت، نه اینکه جوابِ نصف سوالش را بگیرد."""
    seen = scripted(monkeypatch, json.dumps(GOOD))
    result = graph.answer("ا" * (prompts_max() + 1))
    assert result.error is not None
    assert "کوتاه" in result.error
    assert seen == []  # اصلاً به مدل نرفت


def test_a_question_at_the_limit_still_works(wired, monkeypatch):
    scripted(monkeypatch, json.dumps(GOOD))
    assert graph.answer("ا" * prompts_max()).error is None


def prompts_max() -> int:
    import prompts
    return prompts.MAX_QUESTION_CHARS
