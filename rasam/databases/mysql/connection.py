"""اتصال به MySQL / MariaDB از روی رشته‌ی اتصال.

رشته‌ی اتصال شکل `mysql://کاربر:رمز@میزبان:پورت/دیتابیس` دارد؛ درایور `pymysql`
آرگومان‌های جدا می‌خواهد، پس اینجا شکسته می‌شود. **رمز هرگز در پیام خطا نمی‌آید.**
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlsplit

import pymysql
import pymysql.cursors

from rasam.databases.mysql import tls

DEFAULT_PORT = 3306


def parse_uri(uri: str, database: str | None = None) -> dict[str, Any]:
    """آرگومان‌های `pymysql.connect` از روی رشته‌ی اتصال.

    `database` اگر داده شود بر نام دیتابیس داخل رشته مقدم است: نام دیتابیس مال
    پروفایل مشتری است (تصمیم ۸۱) و رشته‌ی اتصال گاهی آن را ندارد. رشته‌ی خالی
    (`""`) یعنی «به هیچ دیتابیسی وصل نشو»، مثلاً وقتی seed می‌خواهد خودِ دیتابیس را بسازد.
    """
    parts = urlsplit(uri)
    if parts.scheme not in ("mysql", "mariadb") or not parts.hostname:
        raise ValueError("رشته‌ی اتصال MySQL باید شکل mysql://کاربر:رمز@میزبان:پورت/دیتابیس داشته باشد.")
    return {
        "host": parts.hostname,
        "port": parts.port or DEFAULT_PORT,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": (database or None) if database is not None else (parts.path.lstrip("/") or None),
        **tls.options(parts.query),
    }


def connect(uri: str, database: str | None = None, timeout_s: int = 5, **extra) -> pymysql.Connection:
    """اتصال با `DictCursor`، و **بدون** چند‌دستوری (پیش‌فرض درایور است و اینجا صریح)."""
    options = parse_uri(uri, database)
    connector = tls.VerifiedConnection if "ssl" in options else pymysql.connect
    return connector(
        **options,
        charset="utf8mb4",
        connect_timeout=timeout_s,
        cursorclass=pymysql.cursors.DictCursor,
        client_flag=0,  # بدون CLIENT.MULTI_STATEMENTS
        # بدون این، هر اتصال در یک تراکنش بازِ همیشگی می‌ماند و اتصال طولانی‌مدت
        # جدول یا دسترسی تازه را نمی‌بیند (snapshot قدیمی). seed خودش commit می‌کند.
        autocommit=True,
        **extra,
    )


def quote_identifier(name: str) -> str:
    """نام جدول یا ستون داخل backtick (`power` و `current` و `timestamp` کلمه‌ی رزرو یا حساس‌اند)."""
    return "`" + name.replace("`", "``") + "`"
