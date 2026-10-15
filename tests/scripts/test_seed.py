"""تست‌های قدم ۲ — روی مونگوی محلیِ پرشده اجرا می‌شوند.

اگر مونگو بالا نباشد یا هنوز seed نشده باشد تست‌ها skip می‌شوند نه fail: نبودنِ
محیط توسعه خطای کد نیست و نباید سبز/قرمز بودن تست‌ها را بی‌معنا کند.

مهم‌ترین تست اینجا `test_readonly_user_cannot_write` است: قاعده‌ی امنیتی ۲ تا
وقتی روی دیتابیس واقعی امتحان نشده، فقط یک ادعا است.
"""

from __future__ import annotations


import pytest
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from rasam import config
from scripts.seed_mongo import collection_name

CSV_FILES = sorted(config.settings.csv_dir.glob("*.csv")) if config.settings.csv_dir else []


@pytest.fixture(scope="module")
def db():
    """اتصال با همان کاربر فقط-خواندنیِ برنامه — نه با کاربر مدیر."""
    client = MongoClient(config.settings.connection_uri, serverSelectionTimeoutMS=2000)
    try:
        client[config.settings.database].list_collection_names()
    except PyMongoError as error:
        pytest.skip(f"مونگوی محلی در دسترس نیست: {error}")
    yield client[config.settings.database]
    client.close()


@pytest.mark.parametrize("csv_path", CSV_FILES, ids=lambda p: collection_name(p))
def test_row_count_matches_csv(db, csv_path):
    """تعداد داکیومنت‌ها باید دقیقاً برابر تعداد ردیف‌های CSV باشد."""
    with csv_path.open(encoding="utf-8") as handle:
        expected = sum(1 for _ in handle) - 1  # منهای سطر عنوان
    assert db[collection_name(csv_path)].count_documents({}) == expected


def test_all_empty_column_is_not_stored(db):
    """`fa_al_message` در کل فایل خالی است، پس نباید اصلاً وارد شده باشد."""
    assert db["inverter_data"].count_documents({"fa_al_message": {"$exists": True}}) == 0


def test_readonly_user_cannot_write(db):
    with pytest.raises(OperationFailure):
        db["inverter_data"].insert_one({"_id": "rasam-write-probe"})


def test_readonly_user_cannot_drop(db):
    with pytest.raises(OperationFailure):
        db["string_data"].drop()
