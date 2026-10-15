"""داده‌ی آزمایشی «دیتابیس محلی» برای ادعاهای رفتاری، به‌ازای هر نوع دیتابیس.

ادعاهای رفتاری (سقف رکورد، شرط سطری) باید روی یک دیتابیس واقعی امتحان شوند. این
جدول می‌گوید روی هر نوع، به کدام دیتابیس وصل شود و با کدام منبع و شرط. **مستقل از
مشتری فعال** است: آداپتور با اتصال صریح ساخته می‌شود (`connection_env` نام متغیر در
`.env` است، بدون پیشوند)، پس یک اجرای `pytest` هر دو دیتابیس را می‌سنجد.
"""

from __future__ import annotations

_TABLES = frozenset({"inverter_data", "lvpanel_data", "mvpanel_data", "string_data"})

LOCAL = {
    "mongodb": {
        "connection_env": "MONGO_URI",
        "database": "solar_telemetry",
        "allowed_sources": _TABLES,
        "source": "inverter_data",
        "filter_field": "work_state",
        "filter_value": "Run",
    },
    "mysql": {
        "connection_env": "MYSQL_URI",
        "database": "solar_telemetry",
        "allowed_sources": _TABLES,
        "source": "inverter_data",
        "filter_field": "work_state",
        "filter_value": "Run",
    },
}
