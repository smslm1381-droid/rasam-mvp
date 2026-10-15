"""تست‌های قدم ۳ — بدون هیچ تماسی با مدل زبانی.

متن ساختار چیزی است که در قدم ۶ وارد پرامپت می‌شود. هر چیزی که اینجا جا بیفتد،
آنجا به شکل کوئری غلط ظاهر می‌شود و عیب‌یابی‌اش سخت است — پس همین‌جا امتحان
می‌شود که به مدل چه گفته‌ایم.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from pymongo.errors import PyMongoError

from rasam.databases.mongodb import schema as mongo_schema


@pytest.fixture(scope="module")
def schema() -> str:
    try:
        return mongo_schema.describe_schema(mongo_schema.connect())
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


def test_only_whitelisted_collections_are_described(monkeypatch):
    """مهم‌ترین تست تازه‌ی این فایل.

    متن ساختار به سرویس مدل *فرستاده می‌شود*، همراه نام فیلدها و یک مقدار
    نمونه. اگر دیتابیس مشتری `users` یا `billing` داشته باشد — و کاربر
    فقط-خواندنی جلوی خواندنشان را نمی‌گیرد — نباید حتی یک نام فیلدشان بیرون
    برود.
    """
    class FakeCollection:
        def find(self):
            return iter([{"secret": "x"}])

        def count_documents(self, _):
            return 1

    class FakeDatabase(dict):
        def list_collection_names(self):
            return ["inverter_data", "billing"]

    fake = FakeDatabase(inverter_data=FakeCollection(), billing=FakeCollection())
    monkeypatch.setattr(mongo_schema.config, "settings",
                        replace(mongo_schema.config.settings,
                                allowed_sources=frozenset({"inverter_data"})))
    text = mongo_schema.describe_schema(fake)
    assert "Collection: inverter_data" in text
    assert "billing" not in text


def test_the_schema_is_derived_once_per_process(monkeypatch):
    """اسکن کامل روی داده‌ی دمو ۳٫۵ ثانیه است؛ هر سوال یک‌بار، غیرقابل قبول."""
    calls = []
    monkeypatch.setattr(mongo_schema, "describe_schema", lambda _: calls.append(1) or "SCHEMA")
    monkeypatch.setattr(mongo_schema, "connect", lambda: None)
    mongo_schema.reset_cache()
    assert mongo_schema.schema_text() == "SCHEMA"
    assert mongo_schema.schema_text() == "SCHEMA"
    assert len(calls) == 1
