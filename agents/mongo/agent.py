"""پیاده‌سازی عملیات MongoDB برای قرارداد DatabaseAgent."""

from __future__ import annotations

from datetime import date, datetime

import config
import db
import guard

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
        return db.schema_text()

    def validate_query(self, collection: str, query: list[dict]) -> guard.Result:
        return guard.check(query, collection, set(config.settings.allowed_collections))

    def execute(self, collection: str, query: list[dict], max_time_ms: int) -> list[dict]:
        database = db.connect()
        rows = database[collection].aggregate(query, maxTimeMS=max_time_ms)
        return [_plain(row) for row in rows]
