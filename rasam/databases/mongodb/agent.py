"""پیاده‌سازی عملیات MongoDB برای قرارداد DatabaseAgent."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pymongo import MongoClient

from rasam import config
from rasam.databases.base import AccessReport, Reply, Result
from rasam.databases.mongodb import guard, prompts, reply, schema

# اکشن‌هایی که نقش داخلی `read` مونگو دارد. هر اکشن دیگر «غیرخواندنی» حساب
# می‌شود، حتی اگر ظاهراً بی‌ضرر باشد: فهرست سفید، نه فهرست سیاه (تصمیم ۸).
READ_ACTIONS = frozenset({
    "find", "listCollections", "listIndexes", "collStats", "dbStats", "dbHash",
    "killCursors", "planCacheRead", "changeStream", "listSearchIndexes",
})

# مقدارهایی که هر سه مقصد خروجی (JSON، CSV، Excel) بدون ترجمه می‌پذیرند.
_PLAIN_TYPES = (str, int, float, bool, datetime, date, type(None))


def _plain(value):
    """مقدار مخصوص مونگو را به مقدار ساده تبدیل می‌کند.

    `_id` یک `ObjectId` است، نه رشته. تا دیروز مسیر خط فرمان آن را با `str()`
    چاپ می‌کرد و کسی متوجه نمی‌شد، ولی دو مقصد دیگر می‌شکستند: API با خطای ۵۰۰
    (`ObjectId` قابل تبدیل به JSON نیست) و خروجی Excel با «Cannot convert».
    همان اتفاق برای `Decimal128` و `Binary` هم می‌افتد.

    ترجمه اینجا انجام می‌شود، نه در لایه‌ی نمایش: نوع‌های مخصوص مونگو دانش
    همین ایجنت‌اند و قاعده‌ی ۴ می‌گوید لایه‌ی نمایش منطقی ندارد. با این کار هر
    سه خروجی از یک ردیفِ یکسان ساخته می‌شوند.
    """
    if isinstance(value, _PLAIN_TYPES):
        return value
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return str(value)


class MongoAgent:
    db_type = "mongodb"

    @staticmethod
    def connection_fields():
        from rasam.databases.connectivity import fields
        return fields(27017)

    @staticmethod
    def build_connection_uri(values):
        from rasam.databases.connectivity import build_uri
        return build_uri("mongodb", values, 27017)

    @staticmethod
    def test_connection(uri, database):
        from rasam.databases.mongodb.connecting import test_connection
        return test_connection(uri, database)

    def __init__(self, connection_uri: str | None = None, database: str | None = None,
                 allowed_sources: frozenset[str] | None = None):
        """بدون آرگومان، مشتری فعال را سرویس می‌دهد.

        آرگومان‌ها فقط برای ابزار تحویل‌اند که باید به دیتابیس یک مشتریِ
        *هنوز فعال‌نشده* وصل شود و `list_sources` و `list_fields` را بپرسد؛ آن
        دو هرگز به تنظیمات مشتری فعال دست نمی‌زنند.
        """
        self._connection_uri = connection_uri
        self._database = database
        self._allowed_sources = allowed_sources

    def _inspect(self, work):
        """یک اتصال کوتاه‌مدت برای ابزار تحویل، که همیشه بسته می‌شود."""
        client = MongoClient(
            self._connection_uri or config.settings.connection_uri, serverSelectionTimeoutMS=5000)
        try:
            return work(client[self._database or config.settings.database])
        finally:
            client.close()

    def check_read_only(self) -> AccessReport:
        status = self._inspect(
            lambda database: database.client.admin.command("connectionStatus", showPrivileges=True))
        info = status["authInfo"]
        if not info["authenticatedUsers"]:
            return AccessReport(False, "اتصال بدون احراز هویت است؛ مونگو بدون auth هر دسترسی را می‌دهد.")
        actions = {action for privilege in info["authenticatedUserPrivileges"]
                   for action in privilege["actions"]}
        extra = sorted(actions - READ_ACTIONS)
        if extra:
            roles = ", ".join(role["role"] for role in info["authenticatedUserRoles"])
            return AccessReport(False, f"نقش‌های «{roles}» اجازه‌ی غیرخواندنی دارند: "
                                       f"{', '.join(extra[:6])}{' …' if len(extra) > 6 else ''}")
        return AccessReport(True, "فقط خواندن (find و ابزارهای مشاهده).")

    def list_sources(self) -> list[str]:
        return sorted(self._inspect(lambda database: database.list_collection_names()))

    def list_fields(self, source: str) -> list[str]:
        return self._inspect(lambda database: schema.field_names(database, source))

    def describe_schema(self) -> str:
        if self._connection_uri is None:
            return schema.schema_text()
        return self._inspect(lambda database: schema.describe_schema(database, self._allowed_sources))

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

    def validate_query(self, source: str, query: list[dict],
                       row_filter: dict | None = None) -> Result:
        allowed = self._allowed_sources or config.settings.allowed_sources
        return guard.check(query, source, set(allowed), row_filter)

    def execute(self, source: str, checked: Result) -> list[dict]:
        if not checked.ok:
            # خطای برنامه‌نویس است نه کاربر: گراف هرگز نباید کوئری ردشده را اینجا بیاورد.
            raise ValueError("execute فقط نتیجه‌ی پذیرفته‌شده‌ی گارد را اجرا می‌کند.")
        def run(database):
            return [_plain(row) for row in
                    database[source].aggregate(checked.query, maxTimeMS=checked.max_time_ms)]

        # بدون اتصال صریح، مشتری فعال (کلاینت مشترک و پایدار)؛ با اتصال صریح، یک
        # اتصال کوتاه‌مدت که بسته می‌شود — برای آزمون انطباق و بررسی آمادگی.
        return run(schema.connect()) if self._connection_uri is None else self._inspect(run)
