"""پرکردن MySQL محلی از همان CSVهای دمو، و ساخت کاربر فقط-خواندنیِ برنامه.

همان ردیف‌هایی که مونگو می‌بیند، به همان شکل: ستون کاملاً خالی ساخته نمی‌شود و
سلول خالی `NULL` است نه `NaN` (`csv_loader`). `tot_reactive_pow` خام و بدون تبدیل
علامت ذخیره می‌شود، مثل مونگو، تا تله‌ی داده و دانشش در هر دو یکی باشد.

مثل `seed_mongo.py`، این تنها جای پروژه است که به دیتابیس می‌نویسد؛ پس اتصال مدیر
را از `RASAM_MYSQL_ADMIN_URI` می‌گیرد، نه از اتصال برنامه.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rasam import config  # noqa: E402
from rasam.databases.mysql import connection  # noqa: E402
from scripts import csv_loader  # noqa: E402

BATCH = 1000
TEXT_LIMIT = 255


def quote(name: str) -> str:
    """نام جدول یا ستون داخل backtick (`power` و `current` و `timestamp` کلمه‌ی رزرو یا حساس‌اند)."""
    return "`" + name.replace("`", "``") + "`"


def column_type(series: pd.Series) -> str:
    """نوع ستون MySQL از روی نوع pandas. رشته‌ی بلند `TEXT` می‌شود، کوتاه `VARCHAR`."""
    if pd.api.types.is_bool_dtype(series):
        return "TINYINT(1)"
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE"
    longest = series.dropna().astype(str).str.len().max()
    return "TEXT" if pd.isna(longest) or longest > TEXT_LIMIT else f"VARCHAR({TEXT_LIMIT})"


def create_table_sql(name: str, frame: pd.DataFrame) -> str:
    columns = ",\n  ".join(f"{quote(c)} {column_type(frame[c])} NULL" for c in frame.columns)
    return (f"CREATE TABLE {quote(name)} (\n  {columns}\n) "
            "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")


def to_python(value):
    """`NaN` ← `None` (NULL)؛ numpy ← نوع پایتون تا درایور بفهمد."""
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def insert_rows(cursor, name: str, frame: pd.DataFrame) -> None:
    columns = ", ".join(quote(c) for c in frame.columns)
    placeholders = ", ".join(["%s"] * len(frame.columns))
    sql = f"INSERT INTO {quote(name)} ({columns}) VALUES ({placeholders})"
    rows = [[to_python(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    for start in range(0, len(rows), BATCH):
        cursor.executemany(sql, rows[start:start + BATCH])


def seed(conn, files: list[Path]) -> list[str]:
    names = []
    with conn.cursor() as cursor:
        for path in files:
            name = csv_loader.table_name(path)
            frame = csv_loader.read_frame(path)
            cursor.execute(f"DROP TABLE IF EXISTS {quote(name)}")
            cursor.execute(create_table_sql(name, frame))
            insert_rows(cursor, name, frame)
            print(f"  {name:<16} {len(frame):>6} ردیف  {len(frame.columns):>4} ستون")
            names.append(name)
    conn.commit()
    return names


def ensure_readonly_user(conn, app_uri: str, database: str, tables: list[str]) -> str:
    """کاربر فقط-خواندنی را از روی خودِ `RASAM_MYSQL_URI` می‌سازد یا به‌روز می‌کند.

    نام و رمز از رشته‌ی اتصال برنامه خوانده می‌شوند (تصمیم ۱۳). دسترسی `SELECT`
    **جدول‌به‌جدول** داده می‌شود نه روی کل دیتابیس، تا جدولی که بعداً اضافه شود
    خودبه‌خود دیده نشود (همان منطق فهرست سفید).
    """
    parsed = connection.parse_uri(app_uri, database)
    user, password = parsed["user"], parsed["password"]
    if not user or not password:
        raise ValueError("RASAM_MYSQL_URI باید نام کاربر و رمز داشته باشد.")
    with conn.cursor() as cursor:
        cursor.execute("CREATE USER IF NOT EXISTS %s@'%%' IDENTIFIED BY %s", (user, password))
        cursor.execute("ALTER USER %s@'%%' IDENTIFIED BY %s", (user, password))
        cursor.execute("REVOKE ALL PRIVILEGES, GRANT OPTION FROM %s@'%%'", (user,))
        for table in tables:
            cursor.execute(f"GRANT SELECT ON {quote(database)}.{quote(table)} TO %s@'%%'", (user,))
        cursor.execute("FLUSH PRIVILEGES")
    return user


def main() -> int:
    admin_uri = config.env_value("MYSQL_ADMIN_URI")
    app_uri = config.env_value("MYSQL_URI")
    if not admin_uri or not app_uri:
        print("خطا: RASAM_MYSQL_ADMIN_URI و RASAM_MYSQL_URI در `.env` لازم‌اند. نوشتن در "
              "دیتابیس به اتصال مدیر نیاز دارد؛ کاربر فقط-خواندنی نمی‌تواند بنویسد.")
        return 1
    if config.settings.csv_dir is None:
        print("خطا: RASAM_CSV_DIR در `.env` نیست. این اسکریپت فقط برای دموست.")
        return 1
    files = sorted(config.settings.csv_dir.glob("*.csv"))
    if not files:
        print(f"خطا: هیچ فایل CSVی در «{config.settings.csv_dir}» پیدا نشد.")
        return 1

    database = connection.parse_uri(app_uri)["database"]
    print(f"خواندن {len(files)} فایل از {config.settings.csv_dir}")
    try:
        with connection.connect(admin_uri, database="") as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {quote(database)} "
                               "DEFAULT CHARACTER SET utf8mb4")
            conn.select_db(database)
            tables = seed(conn, files)
            user = ensure_readonly_user(conn, app_uri, database, tables)
    except pymysql.MySQLError as error:
        code = error.args[0] if error.args and isinstance(error.args[0], int) else "؟"
        print(f"خطا در کار با MySQL ({type(error).__name__}، کد {code}). آیا `docker compose up -d` را زده‌اید؟")
        return 1
    except ValueError as error:
        print(f"خطا: {error}")
        return 1

    print(f"کاربر فقط-خواندنی «{user}» آماده است.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
