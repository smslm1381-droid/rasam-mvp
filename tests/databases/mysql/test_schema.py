"""تست خواندن ساختار MySQL — بدون مدل، روی MySQL محلیِ seed‌شده.

هر چیزی که اینجا جا بیفتد، در پرامپت به شکل کوئری غلط ظاهر می‌شود و عیب‌یابی‌اش
سخت است؛ پس همین‌جا امتحان می‌شود که به مدل چه گفته‌ایم.
"""

from __future__ import annotations

import re

import pymysql
import pytest

from rasam import config
from rasam.databases.mongodb import schema as mongo_schema
from rasam.databases.mysql import connection, schema

ALL_TABLES = frozenset({"inverter_data", "lvpanel_data", "mvpanel_data", "string_data"})


@pytest.fixture(scope="module")
def conn():
    uri = config.env_value("MYSQL_URI")
    if not uri:
        pytest.skip("RASAM_MYSQL_URI در `.env` نیست.")
    try:
        opened = connection.connect(uri)
    except pymysql.MySQLError as error:
        pytest.skip(f"MySQL محلی در دسترس نیست (کد {error.args[0] if error.args else '؟'}).")
    yield opened
    opened.close()


@pytest.fixture(scope="module")
def text(conn) -> str:
    return schema.describe_schema(conn, ALL_TABLES)


def test_every_allowed_table_is_described(text):
    for table in ALL_TABLES:
        assert f"Table: {table} (" in text


def test_known_inverter_fields_are_present(text):
    for field in ("int_temp", "tot_active_pow", "daily_pow_yield", "work_state"):
        assert f"  {field}: " in text


def test_rare_categorical_values_are_listed_from_the_whole_table(text):
    """همان تله‌ی مونگو (تصمیم ۱۶): هر چهار مقدار `work_state` باید دیده شوند."""
    for value in ("Initial standby", "Run", "Standby", "Starting"):
        assert repr(value) in text


def test_repeated_fields_are_written_one_by_one(text):
    for i in range(1, 13):
        assert f"  mppt{i}_volt: " in text and f"  str{i}_current: " in text


def test_the_time_field_ambiguity_is_resolved_by_the_customer_notes(text):
    assert "canonical time field" in text and "prefer `timestamp`" in text


def test_the_dropped_all_empty_column_is_not_described(text):
    assert "fa_al_message" not in text


def test_the_model_sees_the_same_type_names_mongo_uses(text):
    """`bigint` و `double` نه؛ همان `int` و `float` — یک دنیای نوع برای هر دو دیتابیس."""
    types = set(re.findall(r"^  \w+: (\w+) ", text, flags=re.MULTILINE))
    assert types <= {"int", "float", "string", "bool"}, types


def test_only_whitelisted_tables_are_described(conn):
    narrowed = schema.describe_schema(conn, {"inverter_data"})
    assert "Table: inverter_data" in narrowed
    for other in ALL_TABLES - {"inverter_data"}:
        assert other not in narrowed


def test_a_granted_table_outside_the_whitelist_is_never_described(conn):
    """جدول حساس: حتی اگر کاربر خواندنش را داشته باشد، نام ستونش نباید بیرون برود."""
    admin = config.env_value("MYSQL_ADMIN_URI")
    if not admin:
        pytest.skip("RASAM_MYSQL_ADMIN_URI در `.env` نیست.")
    database = connection.parse_uri(config.env_value("MYSQL_URI"))["database"]
    user = connection.parse_uri(config.env_value("MYSQL_URI"))["user"]
    with connection.connect(admin, database=database) as owner, owner.cursor() as cursor:
        cursor.execute("CREATE TABLE `zz_billing` (`card_number` VARCHAR(20))")
        cursor.execute(f"GRANT SELECT ON `{database}`.`zz_billing` TO %s@'%%'", (user,))
        try:
            assert "zz_billing" in schema.present_tables(conn)  # کاربر واقعاً می‌بیند
            assert "card_number" not in schema.describe_schema(conn, ALL_TABLES)
        finally:
            cursor.execute(f"REVOKE SELECT ON `{database}`.`zz_billing` FROM %s@'%%'", (user,))
            cursor.execute("DROP TABLE IF EXISTS `zz_billing`")


def test_the_field_names_match_mongos_fields(conn):
    try:
        mongo_fields = set(mongo_schema.field_names(mongo_schema.connect(), "string_data"))
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"مونگوی محلی در دسترس نیست: {type(error).__name__}")
    assert set(schema.field_names(conn, "string_data")) == mongo_fields


def test_field_lines_agree_with_mongo_on_name_and_type(text):
    """هر فیلد در هر دو دیتابیس همان نوع را دارد؛ وگرنه دانش دمو برای یکی غلط می‌شود."""
    try:
        mongo_text = mongo_schema.describe_schema(mongo_schema.connect())
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"مونگوی محلی در دسترس نیست: {type(error).__name__}")
    pattern = re.compile(r"^  (\w+): (\w+) ", re.MULTILINE)
    mysql_fields = dict(pattern.findall(text))
    mongo_fields = dict(pattern.findall(mongo_text))
    # `_id` در مونگو، فیلدِ CSV است نه شناسه‌ی داخلی؛ هر دو آن را رشته می‌بینند.
    assert mysql_fields == mongo_fields


def test_the_schema_is_derived_once_per_process(monkeypatch):
    calls = []
    monkeypatch.setattr(schema, "describe_schema", lambda *_: calls.append(1) or "SCHEMA")

    class Fake:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(connection, "connect", lambda *_: Fake())
    schema.reset_cache()
    assert schema.schema_text() == schema.schema_text() == "SCHEMA"
    assert len(calls) == 1
    schema.reset_cache()
