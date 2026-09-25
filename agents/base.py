"""قرارداد مشترک عملیات دیتابیس."""

from __future__ import annotations

from typing import Any, Protocol

import guard


class DatabaseAgent(Protocol):
    db_type: str

    def describe_schema(self) -> str: ...

    def validate_query(self, collection: str, query: Any) -> guard.Result: ...

    def execute(self, collection: str, query: Any, max_time_ms: int) -> list[dict]: ...
