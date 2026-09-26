"""پیاده‌سازی عملیات MongoDB برای قرارداد DatabaseAgent."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from rasam import config
from rasam.databases.base import Result
from rasam.databases.mongodb import guard, prompts, schema

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

    def describe_schema(self) -> str:
        return schema.schema_text()

    def build_query_prompt(self, schema_text: str, question: str, collections: set[str],
                           failure: tuple[Any, str] | None = None,
                           want_chart: bool = False,
                           documentation: str | None = None,
                           examples: str | None = None) -> str:
        return prompts.build_query_prompt(
            schema_text, question, collections, failure=failure, want_chart=want_chart,
            documentation=documentation, examples=examples)

    def validate_query(self, collection: str, query: list[dict]) -> Result:
        return guard.check(query, collection, set(config.settings.allowed_collections))

    def execute(self, collection: str, query: list[dict], max_time_ms: int) -> list[dict]:
        database = schema.connect()
        rows = database[collection].aggregate(query, maxTimeMS=max_time_ms)
        return [_plain(row) for row in rows]
