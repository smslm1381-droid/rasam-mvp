"""تست‌های قدم ۳ — بدون هیچ تماسی با مدل زبانی.

متن ساختار چیزی است که در قدم ۶ وارد پرامپت می‌شود. هر چیزی که اینجا جا بیفتد،
آنجا به شکل کوئری غلط ظاهر می‌شود و عیب‌یابی‌اش سخت است — پس همین‌جا امتحان
می‌شود که به مدل چه گفته‌ایم.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pymongo.errors import PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402


@pytest.fixture(scope="module")
def schema() -> str:
    try:
        return db.describe_schema(db.connect())
    except PyMongoError as error:
        pytest.skip(f"مونگوی محلی در دسترس نیست: {error}")


def test_every_collection_is_described(schema):
    for name in ("inverter_data", "lvpanel_data", "mvpanel_data", "string_data"):
        assert f"Collection: {name}" in schema


def test_known_inverter_fields_are_present(schema):
    for field in ("int_temp", "tot_active_pow", "daily_pow_yield", "work_state"):
        assert f"  {field}: " in schema


def test_rare_categorical_values_are_listed(schema):
    """مهم‌ترین تست این قدم.

    `Initial standby` و `Starting` در نمونه‌ی ۵۰۰تایی دیده نمی‌شوند. اگر این
    تست بشکند یعنی برگشته‌ایم به گرفتن مقادیر از نمونه، و سوال درباره‌ی این دو
    حالت بی‌صدا غلط جواب می‌گیرد.
    """
    for value in ("Initial standby", "Run", "Standby", "Starting"):
        assert repr(value) in schema


def test_repeated_fields_are_written_one_by_one(schema):
    """هر ۱۲ ورودی MPPT و هر ۱۲ استرینگ باید جدا نوشته شوند، نه خلاصه."""
    for i in range(1, 13):
        assert f"  mppt{i}_volt: " in schema
        assert f"  str{i}_current: " in schema


def test_time_field_ambiguity_is_resolved(schema):
    """`timestamp` و `ts` هر دو وجود دارند؛ مدل باید بداند کدام مرجع است."""
    assert "canonical time field" in schema
    assert "prefer `timestamp`" in schema


def test_dropped_column_is_not_described(schema):
    assert "fa_al_message" not in schema


def test_no_internal_mongo_type_names_leak(schema):
    """مدل باید `int` ببیند، نه نام کلاس داخلی مونگو مثل `Int64`."""
    assert "Int64" not in schema
