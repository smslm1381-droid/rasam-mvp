"""پیاده‌سازی read-only پایه برای PostgreSQL.

این ایجنت آماده‌ی اتصال است، اما فعال‌کردنش نیازمند پرامپت SQL و پروفایل واقعی
است؛ کد MongoDB نباید به‌خاطر افزودن این backend تغییر کند.
"""

from __future__ import annotations

from typing import Any

import config
import guard


class PostgresAgent:
    db_type = "postgresql"

    def __init__(self, connection_string: str | None = None):
        self.connection_string = connection_string or config.settings.connection_uri

    def describe_schema(self) -> str:
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name, column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                """)
                rows = cursor.fetchall()
        finally:
            connection.close()
        tables: dict[str, list[str]] = {}
        for table, column, data_type in rows:
            tables.setdefault(table, []).append(f"  {column}: {data_type}")
        return "\n\n".join(
            f"Table: {table}\n" + "\n".join(columns)
            for table, columns in tables.items()
        )

    def validate_query(self, collection: str, query: Any) -> guard.Result:
        return guard.Result(False, None, "اعتبارسنجی PostgreSQL هنوز به قرارداد SQL منتقل نشده است.")

    def execute(self, collection: str, query: Any, max_time_ms: int) -> list[dict]:
        raise NotImplementedError("اجرای کوئری PostgreSQL در اتصال SQL قدم بعدی تکمیل می‌شود.")

    def _connect(self):
        import psycopg

        return psycopg.connect(self.connection_string, autocommit=True)
