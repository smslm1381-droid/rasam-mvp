"""این تست‌ها مسیر پاسخِ مدل جعلی را می‌سنجند، نه دقت تشخیص مدل واقعی را."""

from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rasam import config
from rasam.core import graph, llm
from rasam.databases import registry

SCHEMA = "readings: status (string), temperature (number), production (number)"
DIRECT = [
    ("اینورتر چیست؟", "اینورتر دستگاهی است که جریان مستقیم را به جریان متناوب تبدیل می‌کند."),
    ("میانگین با حداکثر چه فرقی دارد؟", "میانگین مقدار متوسط داده‌هاست؛ حداکثر بزرگ‌ترین مقدار آن‌هاست."),
    ("سلام دوست عزیز، چطوری؟", "سلام! ممنون، آماده‌ام به سؤال‌هایتان کمک کنم."),
    ("نمودار مفهومی اینورتر چیست؟", "یک نمودار مفهومی، تبدیل جریان مستقیم به متناوب را نمایش می‌دهد."),
    ("هزینهٔ تعمیر اینورترهای ما چقدر است؟", "اطلاعات هزینهٔ تعمیر در داده‌های موجود نیست."),
    ("اینورتر چیست و هزینهٔ تعمیر امروز ما چقدر بوده؟", "برای پاسخ به بخش هزینهٔ تعمیر، دادهٔ هزینه در دسترس نیست."),
]
DATA_QUESTIONS = [
    "وضعیت اینورترهای ما را توضیح بده",
    "میانگین دما چقدر است؟",
    "اینورتر چیست و تولید امروز ما چقدر بوده؟",
    "وضعیت اینورترهای ما را با نمودار توضیح بده",
]


def wire_nodes(monkeypatch, events):
    def summarize(state):
        events.append("summarize")
        return {"summary": "خلاصهٔ دادهٔ خوانده‌شده."}
    def chart(state):
        events.append("chart")
        return {"chart": {"chart_type": "bar", "x": "status", "y": ["temperature"]}}
    original_repair = graph.repair
    def repair(state):
        events.append("repair")
        return original_repair(state)
    monkeypatch.setattr(graph, "summarize", summarize)
    monkeypatch.setattr(graph, "chart", chart)
    monkeypatch.setattr(graph, "repair", repair)


@pytest.fixture(params=["mongodb", "mysql"])
def wired(request, monkeypatch):
    kind = request.param
    capabilities = frozenset({"summary", "chart", "repair"})
    profile = replace(config.settings.customer, db_type=kind, capabilities=capabilities)
    settings = replace(config.settings, customer=profile,
                       allowed_sources=frozenset({"readings"}), max_attempts=2)
    monkeypatch.setattr(config, "settings", settings)
    agent = registry.AGENTS[kind]()
    monkeypatch.setattr(agent, "describe_schema", Mock(return_value=SCHEMA))
    monkeypatch.setattr(agent, "execute", Mock(return_value=[{"temperature": 28.6}]))
    monkeypatch.setattr(agent, "validate_query", Mock(wraps=agent.validate_query))
    monkeypatch.setattr(graph.registry, "get_agent", lambda: agent)
    monkeypatch.setattr(graph, "_knowledge", lambda *args: {
        "schema": SCHEMA, "documentation": "", "examples": ""})
    model = Mock()
    monkeypatch.setattr(graph.llm, "ask", model)
    events = []
    wire_nodes(monkeypatch, events)
    monkeypatch.setattr(graph, "_GRAPH", graph.build_graph(capabilities))
    return SimpleNamespace(kind=kind, agent=agent, model=model, events=events)


def query_reply(kind, question):
    if "تولید" in question:
        sql = "SELECT SUM(production) AS total FROM readings"
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$production"}}}]
    elif "میانگین" in question:
        sql = "SELECT AVG(temperature) AS average FROM readings"
        pipeline = [{"$group": {"_id": None, "average": {"$avg": "$temperature"}}}]
    else:
        sql = "SELECT status, temperature FROM readings LIMIT 5"
        pipeline = [{"$project": {"_id": 0, "status": 1, "temperature": 1}}, {"$limit": 5}]
    payload = {"table": "readings", "sql": sql} if kind == "mysql" else {
        "collection": "readings", "pipeline": pipeline}
    return llm.Result(True, json.dumps(payload), "")


@pytest.mark.parametrize("question,text", DIRECT)
def test_model_text_stops_before_all_query_and_postprocessing_stages(wired, question, text):
    wired.model.return_value = llm.Result(True, text, "")
    result = graph.answer(question)
    assert result.message == text and result.error is None
    assert result.source is None and result.query is None and result.rows == []
    assert result.summary is None and result.chart is None and not result.repaired
    wired.agent.describe_schema.assert_called_once()
    wired.model.assert_called_once()
    wired.agent.validate_query.assert_not_called()
    wired.agent.execute.assert_not_called()
    assert wired.events == []


@pytest.mark.parametrize("question", DATA_QUESTIONS)
def test_descriptive_statistical_and_mixed_data_answers_still_pass_the_guard(wired, question):
    wired.model.return_value = query_reply(wired.kind, question)
    result = graph.answer(question)
    assert result.rows and result.message is None and result.error is None
    wired.model.assert_called_once()
    wired.agent.validate_query.assert_called_once()
    wired.agent.execute.assert_called_once()
    checked = wired.agent.execute.call_args.args[1]
    assert checked.ok and checked.query == result.query
    assert wired.events == (["summarize", "chart"] if "نمودار" in question else ["summarize"])


def bad_reply(kind):
    payload = {"table": "readings", "sql": "SELECT SLEEP(1) FROM readings"}
    if kind == "mongodb":
        payload = {"collection": "readings", "pipeline": [{"$out": "other"}]}
    return llm.Result(True, json.dumps(payload), "")


def test_a_repaired_query_cannot_bypass_validation(wired):
    wired.model.side_effect = [bad_reply(wired.kind), query_reply(wired.kind, "میانگین دما؟")]
    result = graph.answer("میانگین دما؟")
    assert result.repaired and not result.error
    assert wired.agent.validate_query.call_count == 2
    wired.agent.execute.assert_called_once()
    assert wired.agent.execute.call_args.args[1].ok
    assert wired.events == ["repair", "summarize"]


def test_a_still_forbidden_repair_never_executes(wired):
    wired.model.return_value = bad_reply(wired.kind)
    result = graph.answer("وضعیت اینورترهای ما را توضیح بده")
    assert result.error and result.rows == []
    assert wired.agent.validate_query.call_count == 2
    wired.agent.execute.assert_not_called()
    assert wired.events == ["repair"]


def test_missing_data_during_repair_stops_without_executing_or_summarizing(wired):
    text = "فیلد لازم برای پاسخ به این بخش از سؤال در دسترس نیست."
    wired.model.side_effect = [bad_reply(wired.kind), llm.Result(True, text, "")]
    result = graph.answer("وضعیت اینورترهای ما را توضیح بده")
    assert result.message == text and result.error is None and result.rows == []
    wired.agent.validate_query.assert_called_once()
    wired.agent.execute.assert_not_called()
    assert wired.events == ["repair"]
