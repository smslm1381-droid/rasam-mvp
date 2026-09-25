"""تست قرارداد و رجیستری ایجنت‌های دیتابیس."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from agents.mongo import MongoAgent  # noqa: E402
from agents.postgres import PostgresAgent  # noqa: E402
from agents import registry  # noqa: E402


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