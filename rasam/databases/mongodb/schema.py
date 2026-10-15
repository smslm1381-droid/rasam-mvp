"""اتصال به MongoDB و خواندن ساختارش از روی خودِ داده.

چرا لازم است: مونگو schema ندارد. اگر به مدل نگوییم چه فیلدهایی وجود دارند و
هرکدام چه نوعی‌اند، مدل فیلد از خودش می‌سازد و کوئری بی‌نتیجه برمی‌گردد.

چرا متن خروجی انگلیسی است: مستقیم داخل پرامپت مدل می‌رود.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from rasam import config
from rasam.core import knowledge

# حداکثر مقدار یکتایی که برای یک فیلد در پرامپت فهرست می‌شود. بیشتر از این،
# فیلد متن آزاد است و فهرست‌کردنش هم بی‌فایده است هم پرامپت را می‌ترکاند.
DISTINCT_MAX = 25


@lru_cache(maxsize=1)
def _client() -> MongoClient:
    """کلاینت مونگو یک‌بار ساخته می‌شود و تا پایان فرایند می‌ماند.

    هر `MongoClient` یک استخر اتصال و چند thread دیده‌بان می‌سازد. ساختن آن
    به‌ازای هر تماس، روی خط فرمان فقط کندی است ولی زیر API نشت است: هر درخواست
    چند اتصال باز می‌کند که هیچ‌وقت بسته نمی‌شوند.
    """
    return MongoClient(config.settings.connection_uri, serverSelectionTimeoutMS=5000)


def connect() -> Database:
    """اتصال فقط-خواندنی به دیتابیس مشتری.

    تنها راه رسیدن بقیه‌ی کد به مونگو. رشته‌ی اتصال از کانفیگ می‌آید و کاربرش
    فقط نقش `read` دارد (قاعده‌ی امنیتی ۲).
    """
    return _client()[config.settings.database]


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

    # یادداشت فیلد مال مشتری است نه مال مونگو: `customers/<نام>/field_notes.yaml`
    note = knowledge.field_notes().get(name)
    return f"  {name}: {kind}  {detail}" + (f"  <- {note}" if note else "")


def field_names(db: Database, name: str) -> list[str]:
    """نام فیلدهای یک کالکشن، به ترتیب ظاهرشدن (برای پیش‌نویس مستندات مشتری)."""
    return list(_scan(db[name]))


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
    """متن ساختار کالکشن‌های **مجاز** — همان چیزی که وارد پرامپت می‌شود.

    فقط فهرست سفید توصیف می‌شود، نه هرچه در دیتابیس هست. دو دلیل، و دومی
    مهم‌تر است:

    ۱. مدل نباید کالکشنی را پیشنهاد کند که گارد بعداً ردش می‌کند.
    ۲. این متن **از سرور ما بیرون می‌رود** و به سرویس مدل می‌رسد، همراه نام
       فیلدها و یک مقدار نمونه از هرکدام. دیتابیس مشتری ممکن است `users` یا
       `billing` هم داشته باشد؛ کاربر فقط-خواندنی جلوی خواندنشان را نمی‌گیرد
       (تصمیم ۳۰ نقشه). توصیف‌نکردنشان یعنی حتی یک نام فیلد هم بیرون نمی‌رود.
    """
    present = set(db.list_collection_names()) & set(config.settings.allowed_sources)
    return "\n\n".join(describe_collection(db, name) for name in sorted(present))


@lru_cache(maxsize=1)
def schema_text() -> str:
    """ساختار دیتابیس، یک‌بار در هر فرایند.

    استخراجش کل کالکشن‌ها را می‌خواند (روی داده‌ی دمو ~۳٫۵ ثانیه). بدون این
    حافظه، هر سوال یک اسکن کامل بود و زیر API هر درخواست یکی — گران برای ما و
    فشار بی‌دلیل روی دیتابیس مشتری.

    در عوض، ساختار تازه‌ی دیتابیس با راه‌اندازی دوباره‌ی برنامه دیده می‌شود.
    برای داده‌ی تلمتری که قالبش ثابت است معامله‌ی درستی است؛ اگر روزی مشتری
    ساختار عوض‌شونده داشت، اینجا جای گذاشتن یک زمان انقضاست.
    """
    return describe_schema(connect())


def reset_cache() -> None:
    """پاک‌کردن هر دو حافظه. برای تست و برای جایی که ساختار عوض شده باشد.

    کلاینت پیش از رهاکردن بسته می‌شود؛ وگرنه threadهای دیده‌بانش تا زمان
    جمع‌آوری حافظه زنده می‌مانند — در یک اجرای تست با صدها بار پاک‌کردن، همین
    یعنی صدها thread بی‌صاحب.
    """
    if _client.cache_info().currsize:
        _client().close()
    _client.cache_clear()
    schema_text.cache_clear()


if __name__ == "__main__":
    print(describe_schema(connect()))
