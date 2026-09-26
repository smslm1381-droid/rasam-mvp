"""تنظیم مشترک تست‌ها.

`rasam/databases/mongodb/schema.py` دو چیز را در سطح فرایند نگه می‌دارد: کلاینت مونگو و متن ساختار
دیتابیس. این برای اجرای واقعی درست است (یک اسکن کامل به‌جای یکی در هر سوال)،
ولی بین تست‌ها نشت می‌کند: تستی که دیتابیس جعلی می‌گذارد، متن ساختارِ تست قبلی
را می‌بیند. پس قبل از هر تست هر دو حافظه پاک می‌شوند.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rasam.databases.mongodb import schema as mongo_schema


@pytest.fixture(autouse=True)
def _fresh_db_cache():
    mongo_schema.reset_cache()
    yield
    mongo_schema.reset_cache()
