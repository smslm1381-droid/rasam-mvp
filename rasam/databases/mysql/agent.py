"""پیاده‌سازی عملیات MySQL / MariaDB برای قرارداد DatabaseAgent."""

from __future__ import annotations

import datetime
import decimal
import re
from typing import Any

import pymysql

from rasam import config
from rasam.databases.base import AccessReport, Reply, Result
from rasam.databases.mysql import connection, guard, prompts, reply, schema

# دسترسی‌هایی که کاربر «فقط-خواندنی» اجازه دارد. `USAGE` یعنی «هیچ دسترسی‌ای» و
# MySQL آن را برای هر کاربری می‌نویسد. هر چیز دیگر غیرخواندنی حساب می‌شود، حتی اگر
# بی‌ضرر به نظر برسد: فهرست سفید، نه فهرست سیاه (تصمیم ۸).
READ_PRIVILEGES = frozenset({"SELECT", "USAGE"})

_GRANT = re.compile(r"^GRANT\s+(?P<privileges>.+?)\s+ON\s+(?P<scope>\S+)\s+TO\s", re.IGNORECASE)
_COLUMN_LIST = re.compile(r"\([^)]*\)")


def _plain(value: Any) -> Any:
    """مقدار مخصوص MySQL را به مقدار ساده تبدیل می‌کند.

    `Decimal` به JSON و Excel نمی‌رود. همان درس `ObjectId` در مونگو (تصمیم ۵۵):
    ترجمه داخل ایجنت انجام می‌شود تا هر سه خروجی یک ردیفِ یکسان ببینند.
    """
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (str, int, float, bool, datetime.datetime, datetime.date, type(None))):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


class MySQLAgent:
    db_type = "mysql"

    def __init__(self, connection_uri: str | None = None, database: str | None = None,
                 allowed_sources: frozenset[str] | None = None):
        """بدون آرگومان، مشتری فعال را سرویس می‌دهد؛ با آرگومان، دیتابیس مشتریِ دیگر را
        (ابزار تحویل، بررسی آمادگی، و آزمون انطباق) بی‌آنکه به تنظیمات فعال دست بزند."""
        self._connection_uri = connection_uri
        self._database = database
        self._allowed_sources = allowed_sources

    def _connect(self) -> pymysql.Connection:
        return connection.connect(self._connection_uri or config.settings.connection_uri,
                                  self._database or config.settings.database)

    def _allowed(self) -> frozenset[str]:
        return self._allowed_sources or config.settings.allowed_sources

    # --- ساختار -----------------------------------------------------------

    def describe_schema(self) -> str:
        if self._connection_uri is None:
            return schema.schema_text()
        with self._connect() as conn:
            return schema.describe_schema(conn, self._allowed())

    def list_sources(self) -> list[str]:
        with self._connect() as conn:
            return sorted(schema.present_tables(conn))

    def list_fields(self, source: str) -> list[str]:
        with self._connect() as conn:
            return schema.field_names(conn, source)

    def check_read_only(self) -> AccessReport:
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
            lines = [next(iter(row.values())) for row in cursor.fetchall()]
        extra: set[str] = set()
        for line in lines:
            match = _GRANT.match(line)
            if not match:
                # مثلاً `GRANT role TO user`: شکلِ ناشناخته، پس غیرخواندنی فرض می‌شود.
                return AccessReport(False, "فهرست دسترسی‌ها شکلی دارد که شناخته نمی‌شود (نقش؟)؛ فقط-خواندنی تایید نشد.")
            names = {p.strip().upper() for p in _COLUMN_LIST.sub("", match["privileges"]).split(",")}
            extra |= names - READ_PRIVILEGES
            if re.search(r"WITH\s+GRANT\s+OPTION", line, re.IGNORECASE):
                extra.add("GRANT OPTION")
        if extra:
            ordered = sorted(extra)
            return AccessReport(False, "دسترسی غیرخواندنی دارد: "
                                       f"{', '.join(ordered[:6])}{' …' if len(ordered) > 6 else ''}")
        return AccessReport(True, "فقط SELECT.")

    # --- مدل --------------------------------------------------------------

    def build_query_prompt(self, schema_text: str, question: str, sources: set[str],
                           failure: tuple[Any, str] | None = None,
                           want_chart: bool = False,
                           documentation: str | None = None,
                           examples: str | None = None) -> str:
        return prompts.build_query_prompt(
            schema_text, question, sources, failure=failure, want_chart=want_chart,
            documentation=documentation, examples=examples)

    def format_example(self, example: dict) -> str:
        return prompts.format_example(example)

    def parse_reply(self, text: str) -> Reply:
        return reply.parse_reply(text)

    # --- گارد و اجرا ------------------------------------------------------

    def validate_query(self, source: str, query: str, row_filter: dict | None = None) -> Result:
        return guard.check(query, source, set(self._allowed()), row_filter)

    def execute(self, source: str, checked: Result) -> list[dict]:
        if not checked.ok:
            # خطای برنامه‌نویس است نه کاربر: گراف هرگز نباید کوئری ردشده را اینجا بیاورد.
            raise ValueError("execute فقط نتیجه‌ی پذیرفته‌شده‌ی گارد را اجرا می‌کند.")
        with self._connect() as conn, conn.cursor() as cursor:
            # لایه‌ی دوم کنار کاربر فقط-SELECT (قاعده‌ی ۲: هر دو، نه یکی): خودِ
            # تراکنش فقط-خواندنی است، پس حتی اگر کاربر اشتباهاً دسترسی نوشتن بگیرد
            # این اتصال نمی‌نویسد.
            self._set_time_limit(cursor, checked.max_time_ms)
            cursor.execute("START TRANSACTION READ ONLY")
            try:
                cursor.execute(checked.query)
                rows = cursor.fetchall()
            finally:
                cursor.execute("ROLLBACK")
        return [{key: _plain(value) for key, value in row.items()} for row in rows]

    @staticmethod
    def _set_time_limit(cursor, max_time_ms: int) -> None:
        """سقف زمان کوئری. MySQL میلی‌ثانیه می‌خواهد؛ MariaDB متغیر دیگری دارد، با ثانیه."""
        try:
            cursor.execute("SET SESSION max_execution_time = %s", (int(max_time_ms),))
        except pymysql.MySQLError:
            cursor.execute("SET SESSION max_statement_time = %s", (max_time_ms / 1000,))
