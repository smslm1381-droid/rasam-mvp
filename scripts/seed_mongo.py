"""پرکردن مونگوی محلی از CSVهای دمو، و ساخت کاربر فقط-خواندنیِ برنامه.

چرا اسکریپت جدا و نه بخشی از برنامه: این تنها جای پروژه است که به دیتابیس
می‌نویسد. جدا ماندنش یعنی مسیر عادیِ پاسخ‌دادن به سوال هیچ‌وقت یک اتصال
نویسنده در دست ندارد (قاعده‌ی امنیتی ۲).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# با `python scripts/seed_mongo.py` اجرا می‌شود، پس ریشه‌ی پروژه خودبه‌خود روی
# مسیر ایمپورت نیست.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rasam import config  # noqa: E402


def collection_name(path: Path) -> str:
    """`solar_telemetry.inverter_data.csv` → `inverter_data`.

    فایل‌های دامپ نام دیتابیس را هم جلوی نام کالکشن دارند. آخرین تکه همیشه نام
    کالکشن است؛ همین قاعده برای فایلی به نام `inverter_data.csv` هم کار می‌کند.
    """
    return path.stem.rsplit(".", 1)[-1]


def load_documents(path: Path) -> list[dict]:
    """یک CSV را به فهرست داکیومنت آماده‌ی درج تبدیل می‌کند.

    دو تمیزکاری اینجا انجام می‌شود چون بعداً گران تمام می‌شوند:
    ۱. ستونی که در کل فایل خالی است اصلاً وارد نمی‌شود (مثل `fa_al_message`)،
       وگرنه در قدم ۳ داخل schema می‌آید و مدل روی فیلد پوچ حساب باز می‌کند.
    ۲. سلول خالی حذف می‌شود نه اینکه NaN درج شود؛ NaN در مونگو یک عددِ واقعی
       است و `$avg` و `$max` را بی‌صدا خراب می‌کند.
    """
    frame = pd.read_csv(path, low_memory=False).dropna(axis="columns", how="all")
    return [
        {key: value for key, value in row.items() if pd.notna(value)}
        for row in frame.to_dict("records")
    ]


def ensure_readonly_user(client: MongoClient, app_uri: str, db_name: str) -> str:
    """کاربر فقط-خواندنی را از روی خودِ `RASAM_MONGO_URI` می‌سازد یا به‌روز می‌کند.

    نام و رمز از رشته‌ی اتصال برنامه خوانده می‌شوند تا یک منبع حقیقت داشته
    باشیم؛ رمزی که در دو جا نوشته شود روزی از هم دور می‌افتد.
    کاربر داخل خودِ دیتابیس هدف ساخته می‌شود نه در `admin`، تا اتصال برنامه به
    `authSource` جداگانه نیاز نداشته باشد.
    """
    from pymongo.uri_parser import parse_uri

    parsed = parse_uri(app_uri)
    username, password = parsed["username"], parsed["password"]
    if not username or not password:
        raise ValueError("RASAM_MONGO_URI باید نام کاربری و رمز داشته باشد.")

    database = client[db_name]
    roles = [{"role": "read", "db": db_name}]
    if database.command("usersInfo", username)["users"]:
        database.command("updateUser", username, pwd=password, roles=roles)
    else:
        database.command("createUser", username, pwd=password, roles=roles)
    return username


def seed(client: MongoClient, db_name: str, files: list[Path]) -> None:
    """هر CSV را در کالکشن هم‌نامش می‌ریزد.

    کالکشن اول drop می‌شود تا اجرای دوباره‌ی اسکریپت داده را دو برابر نکند.
    """
    database = client[db_name]
    for path in files:
        name = collection_name(path)
        documents = load_documents(path)
        database[name].drop()
        database[name].insert_many(documents)
        print(f"  {name:<16} {len(documents):>6} داکیومنت")


def main() -> int:
    settings = config.settings

    if not settings.mongo_admin_uri:
        print("خطا: RASAM_MONGO_ADMIN_URI در `.env` نیست. نوشتن در دیتابیس به"
              " اتصال مدیر نیاز دارد؛ کاربر فقط-خواندنی نمی‌تواند بنویسد.")
        return 1

    if settings.csv_dir is None:
        print("خطا: RASAM_CSV_DIR در `.env` نیست. این اسکریپت فقط برای دموست و CSVها را از آنجا می‌خواند.")
        return 1

    files = sorted(settings.csv_dir.glob("*.csv"))
    if not files:
        print(f"خطا: هیچ فایل CSVی در «{settings.csv_dir}» پیدا نشد."
              " مقدار RASAM_CSV_DIR را در `.env` درست کنید.")
        return 1

    print(f"خواندن {len(files)} فایل از {settings.csv_dir}")
    try:
        with MongoClient(settings.mongo_admin_uri, serverSelectionTimeoutMS=5000) as client:
            seed(client, settings.database, files)
            user = ensure_readonly_user(client, settings.connection_uri, settings.database)
    except PyMongoError as error:
        print(f"خطا در کار با مونگو: {error}\nآیا `docker compose up -d` را زده‌اید؟")
        return 1
    except ValueError as error:
        print(f"خطا: {error}")
        return 1

    print(f"کاربر فقط-خواندنی «{user}» آماده است.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
