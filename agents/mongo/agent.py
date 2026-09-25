"""پیاده‌سازی عملیات MongoDB برای قرارداد DatabaseAgent."""

from __future__ import annotations

from pymongo.errors import PyMongoError

import config
import db
import guard


class MongoAgent:
    db_type = "mongodb"

    def describe_schema(self) -> str:
        return db.describe_schema(db.connect())

    def validate_query(self, collection: str, query: list[dict]) -> guard.Result:
        return guard.check(query, collection, set(config.settings.allowed_collections))

    def execute(self, collection: str, query: list[dict], max_time_ms: int) -> list[dict]:
        database = db.connect()
        return list(database[collection].aggregate(query, maxTimeMS=max_time_ms))


def is_database_error(error: Exception) -> bool:
    return isinstance(error, PyMongoError)