"""تست قرارداد و رجیستری ایجنت‌های دیتابیس."""

from __future__ import annotations

from datetime import datetime

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128

from rasam import config, customer
from rasam.databases.mongodb import MongoAgent
from rasam.databases.mysql import MySQLAgent
from rasam.databases.mongodb import agent as agent_module
from rasam.databases import registry
from rasam.databases.base import Result


def test_registry_selects_mongodb_from_demo_profile():
    assert isinstance(registry.get_agent(), MongoAgent)


def test_only_adapters_that_pass_conformance_are_registered():
    """آداپتوری که آزمون انطباق را سبز نکرده در رجیستری نیست."""
    assert registry.AGENTS == {"mongodb": MongoAgent, "mysql": MySQLAgent}
    assert config.settings.customer.db_type == "mongodb"


def test_a_profile_asking_for_an_unregistered_database_fails_at_startup():
    profile = customer.CustomerProfile(
        **{**config.settings.customer.__dict__, "db_type": "oracle"})
    with pytest.raises(config.ConfigError, match="oracle"):
        registry.check_db_type(profile)


class _Collection:
    def __init__(self, rows):
        self.rows = rows

    def aggregate(self, pipeline, maxTimeMS=None):  # noqa: N803 — امضای pymongo
        return iter(self.rows)


def test_mongo_only_types_leave_the_agent_as_plain_values(monkeypatch):
    """`_id` یک ObjectId است، نه رشته.

    تا دیروز خط فرمان با `str()` چاپش می‌کرد و کسی نمی‌فهمید، ولی API با ۵۰۰
    و خروجی Excel با «Cannot convert» می‌شکستند. ترجمه باید همین‌جا انجام شود
    تا هر سه خروجی یک ردیفِ یکسان ببینند.
    """
    identifier = ObjectId()
    rows = [{"_id": identifier, "amount": Decimal128("12.5"),
             "when": datetime(2025, 1, 1), "n": 3,
             "nested": {"id": identifier}, "many": [identifier]}]
    monkeypatch.setattr(agent_module.schema, "connect",
                        lambda: {"inverter_data": _Collection(rows)})
    accepted = Result(ok=True, query=[{"$match": {}}], reason="", max_time_ms=1000)
    row = MongoAgent().execute("inverter_data", accepted)[0]

    assert row["_id"] == str(identifier)
    assert row["amount"] == "12.5"
    assert row["when"] == datetime(2025, 1, 1)  # تاریخ را هر سه خروجی می‌فهمند
    assert row["n"] == 3
    assert row["nested"] == {"id": str(identifier)}
    assert row["many"] == [str(identifier)]


def test_the_agent_asks_for_the_cached_schema_not_a_fresh_scan(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_module.schema, "schema_text",
                        lambda: calls.append(1) or "SCHEMA")
    assert MongoAgent().describe_schema() == "SCHEMA"
    assert len(calls) == 1


def test_execute_refuses_a_query_the_guard_did_not_accept():
    """قاعده‌ی ۳ در امضای تابع: اجرا فقط از روی نتیجه‌ی پذیرفته‌شده‌ی گارد."""
    rejected = Result(ok=False, query=None, reason="رد شد")
    with pytest.raises(ValueError, match="پذیرفته"):
        MongoAgent().execute("inverter_data", rejected)


def test_the_agent_formats_an_example_in_the_shape_the_model_must_answer_in():
    text = MongoAgent().format_example({
        "question": "دما؟", "why": "ساده", "source": "inverter_data",
        "query": [{"$limit": 1}]})
    assert text.startswith("Q: دما؟")
    assert '"collection": "inverter_data"' in text and '"pipeline": [{"$limit": 1}]' in text
    assert "# ساده" in text
