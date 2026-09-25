"""تنظیم مشترک تست‌ها.

`db.py` دو چیز را در سطح فرایند نگه می‌دارد: کلاینت مونگو و متن ساختار
دیتابیس. این برای اجرای واقعی درست است (یک اسکن کامل به‌جای یکی در هر سوال)،
ولی بین تست‌ها نشت می‌کند: تستی که دیتابیس جعلی می‌گذارد، متن ساختارِ تست قبلی
را می‌بیند. پس قبل از هر تست هر دو حافظه پاک می‌شوند.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db_cache():
    db.reset_cache()
    yield
    db.reset_cache()
