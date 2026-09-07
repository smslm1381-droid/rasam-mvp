"""خواندن ساختار دیتابیس از روی خودِ داده.

چرا لازم است: مونگو schema ندارد. اگر به مدل نگوییم چه فیلدهایی وجود دارند و
هرکدام چه نوعی‌اند، مدل فیلد از خودش می‌سازد و کوئری بی‌نتیجه برمی‌گردد.

چرا متن خروجی انگلیسی است: مستقیم داخل پرامپت مدل می‌رود.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from pymongo import MongoClient
from pymongo.database import Database

import config

# حداکثر مقدار یکتایی که برای یک فیلد در پرامپت فهرست می‌شود. بیشتر از این،
# فیلد متن آزاد است و فهرست‌کردنش هم بی‌فایده است هم پرامپت را می‌ترکاند.
DISTINCT_MAX = 25

# این نکته‌ها از تجربه‌ی نسخه‌ی ۱ می‌آیند (docs/v1-reference.md بخش ۱٫۴). اگر
# گفته نشوند مدل همان اشتباه‌ها را تکرار می‌کند: سردرگمی بین دو فیلد زمان، و
# مقایسه‌ی یک عدد صحیح با رشته که همیشه نتیجه‌ی خالی می‌دهد.
FIELD_NOTES = {
    "timestamp": "canonical time field — use this one",
    "ts": "secondary clock, within 5s of `timestamp`; prefer `timestamp`",
    "fa_al_code": "integer, not string — compare with 0, not \"0\"",
}



def connect() -> Database:
    """اتصال فقط-خواندنی به دیتابیس مشتری.

    تنها راه رسیدن بقیه‌ی کد به مونگو. رشته‌ی اتصال از کانفیگ می‌آید و کاربرش
    فقط نقش `read` دارد (قاعده‌ی امنیتی ۲).
    """
    client = MongoClient(config.settings.mongo_uri, serverSelectionTimeoutMS=5000)
    return client[config.settings.mongo_db]


def _type_name(value) -> str:
    """نام نوع، آن‌طور که مدل باید ببیند.

    `bool` قبل از `int` چک می‌شود چون در پایتون زیرمجموعه‌ی آن است. مقدارهای
    بزرگ هم از مونگو به‌صورت `Int64` برمی‌گردند که باز زیرمجموعه‌ی `int` است؛
    اگر نام کلاس را خام بنویسیم مدل یک نوع ناآشنا می‌بیند که وجود خارجی ندارد.
    """
    for kind, name in ((bool, "bool"), (int, "int"), (float, "float"), (str, "string")):
        if isinstance(value, kind):
            return name
    return type(value).__name__


def _scan(collection) -> dict[str, dict]:
    """یک بار خواندن کل کالکشن و جمع‌کردن هرچه برای توصیف لازم است.

    چرا کل کالکشن و نه نمونه: ابتدای کالکشن یک بازه‌ی زمانی باریک است. هم
    مقدار کمیاب را نمی‌بیند (`work_state` در ۵۰۰ داکیومنت اول فقط یک مقدار
    دارد ولی در کل داده چهار تا)، و هم فیلدی را که در ردیف‌های اول خالی بوده
    کلاً از قلم می‌اندازد — آن‌وقت مدل از وجودش بی‌خبر می‌ماند. اسکن کامل روی
    این داده کمتر از نیم ثانیه است و یک‌بار انجام می‌شود.
    """
    stats: dict[str, dict] = {}
    for document in collection.find():
        for key, value in document.items():
            if value is None:
                continue
            field = stats.setdefault(key, {"types": Counter(), "example": value, "values": set()})
            field["types"][_type_name(value)] += 1
            # مقادیر یکتا فقط تا یکی بیشتر از سقف جمع می‌شوند؛ از آن به بعد
            # می‌دانیم متن آزاد است و ادامه‌اش فقط حافظه می‌خورد.
            if isinstance(value, str) and len(field["values"]) <= DISTINCT_MAX:
                field["values"].add(value)
    return stats


def _field_line(name: str, field: dict) -> str:
    """یک خط توصیف فیلد: نوع، و یا فهرست کامل مقادیر یا یک نمونه."""
    kind = field["types"].most_common(1)[0][0]
    values = field["values"]

    if kind == "string" and 0 < len(values) <= DISTINCT_MAX:
        detail = "one of: " + ", ".join(repr(v) for v in sorted(values))
    else:
        detail = f"e.g. {field['example']!r}"

    note = FIELD_NOTES.get(name)
    return f"  {name}: {kind}  {detail}" + (f"  <- {note}" if note else "")


def describe_collection(db: Database, name: str) -> str:
    """ساختار یک کالکشن به‌صورت متن.

    فیلدها به ترتیب ظاهرشدنشان در داکیومنت می‌آیند، چون ترتیب طبیعیِ داده برای
    خواندن آسان‌تر از ترتیب الفبایی است.
    """
    collection = db[name]
    stats = _scan(collection)
    header = f"Collection: {name} ({collection.count_documents({})} documents)"
    return "\n".join([header] + [_field_line(k, v) for k, v in stats.items()])


def describe_schema(db: Database) -> str:
    """متن ساختار همه‌ی کالکشن‌ها — همان چیزی که در قدم ۶ وارد پرامپت می‌شود."""
    return "\n\n".join(
        describe_collection(db, name) for name in sorted(db.list_collection_names())
    )


if __name__ == "__main__":
    print(describe_schema(connect()))
