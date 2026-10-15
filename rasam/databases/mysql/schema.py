"""خواندن ساختار دیتابیس MySQL.

همان کار `mongodb/schema.py` برای SQL، با یک فرق: MySQL خودش schema دارد و لازم
نیست از روی داده حدسش بزنیم. ولی دو درس مونگو همچنان معتبرند:

- **فقط جدول‌های فهرست سفید توصیف می‌شوند** (تصمیم ۵۲). این متن به سرویس مدل
  می‌رود، همراه نام ستون‌ها و یک مقدار نمونه؛ جدول حساسِ مشتری نباید حتی یک نام
  ستونش بیرون برود.
- **فهرست کامل مقادیر یک ستون متنیِ کم‌تنوع از کل جدول گرفته می‌شود** (تصمیم ۱۶)، نه از یک نمونه.

خروجی انگلیسی و هم‌شکل خروجی مونگو است (`Table:` به‌جای `Collection:`) تا پرامپت
عوض نشود، و چون مستقیم داخل پرامپت مدل می‌رود.
"""

from __future__ import annotations

import datetime
import decimal
from functools import lru_cache

from rasam import config
from rasam.core import knowledge
from rasam.databases.mysql import connection

# بیشتر از این مقدار یکتا یعنی متن آزاد است و فهرست‌کردنش بی‌فایده و پرامپت‌ترکان.
DISTINCT_MAX = 25

_INT = {"tinyint", "smallint", "mediumint", "int", "integer", "bigint"}
_FLOAT = {"float", "double", "decimal", "numeric"}
_STRING = {"char", "varchar", "tinytext", "text", "mediumtext", "longtext", "enum", "set"}


def type_name(data_type: str, column_type: str) -> str:
    """نام نوع، آن‌طور که مدل باید ببیند — همان نام‌های مونگو، نه نام خام MySQL.

    اگر `bigint` و `double` را خام بنویسیم، مدل دو دنیای نوع می‌بیند و برای هر
    دیتابیس چیز دیگری یاد می‌گیرد؛ همان اشتباهی که `Int64` در مونگو می‌ساخت.
    """
    kind = data_type.lower()
    if kind == "tinyint" and column_type.lower().startswith("tinyint(1)"):
        return "bool"
    if kind in _INT:
        return "int"
    if kind in _FLOAT:
        return "float"
    if kind in _STRING:
        return "string"
    return kind


def _shown(value) -> str:
    """مقدار نمونه برای مدل. تاریخ و Decimal به شکل ساده می‌آیند، نه `datetime.datetime(…)`."""
    if isinstance(value, decimal.Decimal):
        return repr(float(value))
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)):
        return repr(str(value))
    return repr(value)


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def present_tables(conn) -> set[str]:
    """جدول‌هایی که این کاربر در دیتابیس جاری می‌بیند. (کاربر فقط-خواندنی فقط جدول‌های `GRANT`شده را می‌بیند.)"""
    rows = _rows(conn, "SELECT table_name AS name FROM information_schema.tables "
                       "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'")
    return {row["name"] for row in rows}


def columns(conn, table: str) -> list[tuple[str, str, str]]:
    """(نام، DATA_TYPE، COLUMN_TYPE) به ترتیب ستون‌ها در جدول."""
    rows = _rows(conn, "SELECT column_name AS name, data_type AS kind, column_type AS full "
                       "FROM information_schema.columns "
                       "WHERE table_schema = DATABASE() AND table_name = %s "
                       "ORDER BY ordinal_position", (table,))
    return [(row["name"], row["kind"], row["full"]) for row in rows]


def _example(conn, table: str, column: str):
    quoted = connection.quote_identifier(column)
    rows = _rows(conn, f"SELECT {quoted} AS v FROM {connection.quote_identifier(table)} "
                       f"WHERE {quoted} IS NOT NULL LIMIT 1")
    return rows[0]["v"] if rows else None


def _distinct(conn, table: str, column: str) -> list[str] | None:
    """همه‌ی مقدارهای یکتا، اگر کم‌اند؛ وگرنه None (متن آزاد)."""
    quoted = connection.quote_identifier(column)
    rows = _rows(conn, f"SELECT DISTINCT {quoted} AS v FROM {connection.quote_identifier(table)} "
                       f"WHERE {quoted} IS NOT NULL LIMIT {DISTINCT_MAX + 1}")
    values = sorted(str(row["v"]) for row in rows)
    return values if 0 < len(values) <= DISTINCT_MAX else None


def _field_line(conn, table: str, column: tuple[str, str, str]) -> str:
    name, data_type, column_type = column
    kind = type_name(data_type, column_type)
    values = _distinct(conn, table, name) if kind == "string" else None
    detail = ("one of: " + ", ".join(repr(v) for v in values)) if values else \
        f"e.g. {_shown(_example(conn, table, name))}"
    note = knowledge.field_notes().get(name)
    return f"  {name}: {kind}  {detail}" + (f"  <- {note}" if note else "")


def describe_table(conn, table: str) -> str:
    """ساختار یک جدول به‌صورت متن، فیلدها به ترتیب ستون در جدول."""
    count = _rows(conn, f"SELECT COUNT(*) AS n FROM {connection.quote_identifier(table)}")[0]["n"]
    header = f"Table: {table} ({count} rows)"
    return "\n".join([header] + [_field_line(conn, table, column) for column in columns(conn, table)])


def describe_schema(conn, allowed_sources: frozenset[str] | set[str]) -> str:
    """متن ساختار جدول‌های **مجاز** — همان چیزی که وارد پرامپت می‌شود."""
    tables = sorted(present_tables(conn) & set(allowed_sources))
    return "\n\n".join(describe_table(conn, table) for table in tables)


def field_names(conn, table: str) -> list[str]:
    """نام ستون‌های یک جدول (برای پیش‌نویس مستندات مشتری)."""
    return [name for name, _, _ in columns(conn, table)]


@lru_cache(maxsize=1)
def schema_text() -> str:
    """ساختار دیتابیس مشتری فعال، یک‌بار در هر فرایند (درس تصمیم ۵۴)."""
    settings = config.settings
    with connection.connect(settings.connection_uri, settings.database) as conn:
        return describe_schema(conn, settings.allowed_sources)


def reset_cache() -> None:
    schema_text.cache_clear()
