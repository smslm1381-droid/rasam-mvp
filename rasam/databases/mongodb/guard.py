"""دروازه‌ی امنیتی بین مدل و دیتابیس.

از قدم ۶ به بعد، کوئری‌ها را مدل زبانی می‌نویسد. مدل را می‌شود فریب داد — چه با
سوال کاربر و چه با متنی که داخل خودِ داکیومنت‌های دیتابیس نشسته. پس هیچ کوئری
تولیدشده بدون رد شدن از این فایل اجرا نمی‌شود.

روش، **فهرست سفید** است نه فهرست سیاه (تصمیم ۸ نقشه): هر چیزی که صریحاً مجاز
نشده، رد می‌شود. بدترین حالت این روش، ردکردن یک کوئری سالم است؛ بدترین حالت
فهرست سیاه، لو رفتن داده‌ی مشتری.

اینجا هیچ‌چیز اجرا نمی‌شود — نه `eval`، نه `exec`. فقط ساختار داده بازبینی
می‌شود.
"""

from __future__ import annotations

from typing import Any

from rasam import config
from rasam.databases.base import Result

# ---------------------------------------------------------------------------
# فهرست‌های سفید
# ---------------------------------------------------------------------------

# فقط این stageها. `$lookup`، `$facet`، `$bucket` و `$skip` عمداً نیستند: هر
# stage تازه یک سطح حمله‌ی تازه است و وقتی اضافه می‌شود که سوالی واقعاً به آن
# نیاز داشته باشد — و آن‌وقت تست‌های خودش را می‌آورد.
ALLOWED_STAGES = frozenset({
    "$match", "$group", "$sort", "$limit",
    "$project", "$addFields", "$unwind", "$count",
})

# اینها هرگز مجاز نیستند، در هیچ عمقی — و هرکدام دلیل خودش را همراه دارد تا
# پیام رد، مبهم نماند. سه‌تای اول کد اجرا می‌کنند، دوتای آخر می‌نویسند.
FORBIDDEN_REASONS = {
    "$where": "کد جاوااسکریپت را روی سرور دیتابیس اجرا می‌کند",
    "$function": "کد جاوااسکریپت را روی سرور دیتابیس اجرا می‌کند",
    "$accumulator": "کد جاوااسکریپت را روی سرور دیتابیس اجرا می‌کند",
    "$out": "یک کوئری خواندنی را به نوشتن تبدیل می‌کند",
    "$merge": "یک کوئری خواندنی را به نوشتن تبدیل می‌کند",
}

# از روی همان دیکشنری ساخته می‌شود تا این دو هیچ‌وقت از هم دور نیفتند: اگر
# روزی موردی اضافه شود، بدون دلیل نمی‌ماند.
FORBIDDEN = frozenset(FORBIDDEN_REASONS)

_COMPARISON = {"$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin"}
_LOGICAL = {"$and", "$or", "$not", "$nor", "$expr"}
_ELEMENT = {"$exists", "$type", "$regex", "$options", "$all", "$elemMatch", "$size"}
_ARITHMETIC = {
    "$add", "$subtract", "$multiply", "$divide", "$mod", "$abs", "$ceil",
    "$floor", "$round", "$trunc", "$sqrt", "$pow", "$exp", "$ln", "$log", "$log10",
}
_ACCUMULATORS = {
    "$sum", "$avg", "$min", "$max", "$first", "$last",
    "$push", "$addToSet", "$count", "$stdDevPop", "$stdDevSamp",
}
_CONDITIONAL = {"$cond", "$ifNull", "$switch", "$case", "$then", "$default"}
_DATE = {
    "$year", "$month", "$dayOfMonth", "$dayOfWeek", "$dayOfYear", "$week",
    "$hour", "$minute", "$second", "$millisecond",
    "$dateToString", "$dateFromString", "$dateFromParts", "$dateToParts",
    "$toDate", "$dateTrunc", "$dateDiff", "$dateAdd", "$dateSubtract",
}
_STRING = {
    "$concat", "$substr", "$substrCP", "$strLenCP", "$split",
    "$toLower", "$toUpper", "$trim", "$ltrim", "$rtrim", "$strcasecmp",
}
_CONVERT = {"$toInt", "$toLong", "$toDouble", "$toDecimal", "$toString", "$toBool", "$convert"}
_ARRAY = {"$arrayElemAt", "$slice", "$filter", "$map", "$reduce", "$concatArrays", "$isArray", "$range"}
# `$meta` اینجا نیست: فقط با جست‌وجوی متنی معنا دارد و `$text` مجاز نیست.
_MISC = {"$literal", "$let", "$cmp"}

# سخاوتمند نسبت به محاسبات، سخت‌گیر نسبت به هر چیزی که کد اجرا کند.
ALLOWED_OPERATORS = frozenset(
    _COMPARISON | _LOGICAL | _ELEMENT | _ARITHMETIC | _ACCUMULATORS
    | _CONDITIONAL | _DATE | _STRING | _CONVERT | _ARRAY | _MISC
)


def _reject(reason: str) -> Result:
    return Result(ok=False, query=None, reason=reason)


def _forbidden_key(node: Any) -> str | None:
    """اولین کلید ممنوع یا ناشناخته را در هر عمقی پیدا می‌کند.

    بازگشتی است چون `$where` می‌تواند چند لایه تودرتو داخل `$match` پنهان شود
    و بازبینیِ فقط سطح اول، دقیقاً همان چیزی است که مهاجم رویش حساب می‌کند.
    فقط *کلیدها* بررسی می‌شوند: رشته‌ای مثل `"$int_temp"` ارجاع به فیلد است
    نه اپراتور.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.startswith("$"):
                if key in FORBIDDEN:
                    return key
                if key not in ALLOWED_OPERATORS:
                    return key
            found = _forbidden_key(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _forbidden_key(item)
            if found:
                return found
    return None


def _why_rejected(key: str, kind: str) -> str:
    """پیام رد، با تفکیک دو حالتی که قاطی‌کردنشان گمراه‌کننده است.

    «در فهرست ممنوع» یعنی این هرگز مجاز نخواهد شد و دلیلش امنیتی است.
    «در فهرست مجاز نیست» یعنی شناخته‌شده نیست — شاید فقط از قلم افتاده و
    روزی با تست خودش اضافه شود. `kind` هم می‌گوید مرحله بود یا عملگر، چون
    جای اصلاحشان در کوئری فرق می‌کند.
    """
    if key in FORBIDDEN:
        return f"{kind} «{key}» در فهرست ممنوع است: {FORBIDDEN_REASONS[key]}."
    return f"{kind} «{key}» در فهرست مجاز نیست."


def _check_stages(pipeline: list) -> Result | None:
    """هر مرحله‌ی pipeline را می‌سنجد؛ اولین ایراد را رد می‌کند، یا None اگر همه سالم‌اند."""
    for stage in pipeline:
        if not isinstance(stage, dict) or len(stage) != 1:
            return _reject("هر مرحله باید یک دیکشنری با دقیقاً یک کلید باشد.")

        (name, body), = stage.items()
        if name not in ALLOWED_STAGES:
            return _reject(_why_rejected(name, "مرحله"))

        found = _forbidden_key(body)
        if found:
            return _reject(_why_rejected(found, "عملگر"))
    return None


def _inject_limits(pipeline: list, row_filter: dict | None) -> list:
    """شرط سطری را به ابتدا و سقف رکورد را به انتهای pipeline می‌افزاید."""
    safe = list(pipeline)
    if row_filter:
        safe.insert(0, {"$match": row_filter})

    # سقف در **انتها** می‌نشیند تا هر چه stageهای قبلی تولید کرده‌اند را ببرد.
    # اگر `max_rows` تنظیم نشده باشد سقفی اعمال نمی‌شود — بررسی آمادگی تحویل
    # (`onboard.py check`) تحویل با سقف خاموش را قرمز می‌کند (تصمیم ۶۹).
    max_rows = config.settings.max_rows
    if max_rows is not None:
        safe.append({"$limit": max_rows})
    return safe


def check(
    pipeline: Any,
    collection: str,
    allowed_collections: set[str],
    row_filter: dict | None = None,
) -> Result:
    """بازبینی یک pipeline پیش از اجرا. تنها راه رسیدن کوئری به دیتابیس.

    `row_filter` شرط اجباری سطح-ردیف است (مثلاً `{"plant_id": 3}`) و به
    **ابتدای** pipeline تزریق می‌شود تا هیچ stage بعدی نتواند دورش بزند.
    فعلاً همیشه `None` است؛ در قدم ۱۳ که هویت کاربر آمد پر می‌شود.
    """
    # `collection` را مدل می‌نویسد، پس هر چیزی می‌تواند باشد (فهرست، دیکشنری، عدد).
    # بدون این بررسی، `in` روی یک فهرست استثنای unhashable می‌داد — و گارد
    # هرگز نباید استثنا بدهد (قاعده‌ی ۷). این را آزمون انطباق پیدا کرد.
    if not isinstance(collection, str) or collection not in allowed_collections:
        shown = collection if isinstance(collection, str) else type(collection).__name__
        return _reject(f"کالکشن «{shown}» جزو کالکشن‌های مجاز نیست.")

    if not isinstance(pipeline, list) or not pipeline:
        return _reject("کوئری باید یک فهرست ناخالی از مرحله‌ها باشد.")

    rejection = _check_stages(pipeline)
    if rejection:
        return rejection

    safe = _inject_limits(pipeline, row_filter)

    return Result(
        ok=True,
        query=safe,
        reason="",
        max_time_ms=config.settings.query_timeout_ms,
    )
