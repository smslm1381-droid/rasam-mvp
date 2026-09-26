"""تست قرارداد و رجیستری ایجنت‌های دیتابیس."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from bson import ObjectId
from bson.decimal128 import Decimal128

from rasam import config
from rasam.databases.mongodb import MongoAgent
from rasam.databases.mongodb import agent as agent_module
from rasam.databases.postgresql import PostgresAgent
from rasam.databases import registry


def test_registry_selects_mongodb_from_demo_profile():
    assert isinstance(registry.get_agent(), MongoAgent)


def test_postgres_agent_rejects_queries_until_sql_guard_exists():
    result = PostgresAgent("postgresql://example").validate_query("telemetry", "SELECT 1")
    assert result.ok is False
    assert result.pipeline is None


def test_registry_has_a_distinct_postgresql_backend():
    assert registry.AGENTS["mongodb"] is MongoAgent
    assert registry.AGENTS["postgresql"] is PostgresAgent
    assert config.settings.customer.db_type == "mongodb"


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
    row = MongoAgent().execute("inverter_data", [{"$match": {}}], 1000)[0]

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
