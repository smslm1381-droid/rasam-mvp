"""دروازه‌ی امنیتی بین مدل و MySQL.

همان نقش `mongodb/guard.py` برای SQL: هیچ کوئری تولیدشده بدون رد شدن از این فایل
اجرا نمی‌شود. روش هم همان است — **فهرست سفید، نه فهرست سیاه** (تصمیم ۸): هر چیزی که
صریحاً مجاز نشده رد می‌شود. فقط واحدِ بازبینی فرق می‌کند: مونگو کوئری را به‌صورت
داده می‌گیرد، ولی SQL **متن** است و متن را نمی‌شود با جست‌وجو امن کرد (کامنت، نقل‌قول،
backtick و حروف بزرگ و کوچک هر فیلتر متنی را دور می‌زنند). پس:

۱. متن با `sqlglot` به **درخت نحوی** پارس می‌شود.
۲. **هر گره‌ی** درخت باید در فهرست سفید باشد (پیش‌فرض: رد).
۳. چیزی که اجرا می‌شود **SQLِ بازتولیدشده از همان درخت** است، نه متن مدل. کامنتِ
   اجراشدنی (`/*! … */`) و hint بهینه‌ساز (`/*+ SET_VAR(…) */`) که MySQL اجرایشان
   می‌کند، در درخت نمی‌آیند یا رد می‌شوند.
۴. SQLِ بازتولیدشده دوباره پارس و دوباره بازبینی می‌شود: چیزی که اجرا می‌شود
   دقیقاً همان فهرست سفید را گذرانده است.

اینجا هیچ‌چیز اجرا نمی‌شود. سنجش‌های مدل تهدید (روی MySQL محلی با `rasam_ro`) در بخش ۴ `PLAN.md` است.
"""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp

from rasam import config
from rasam.databases.base import Result

DIALECT = "mysql"
MAX_SQL_CHARS = 20_000

# ---------------------------------------------------------------------------
# فهرست سفید
# ---------------------------------------------------------------------------

# تابع‌های مجاز: نام SQL ← گره‌های درختی که sqlglot برایش می‌سازد. هم فهرست سفید
# گره‌هاست و هم متنی که در پرامپت به مدل نشان داده می‌شود — از همین یک دیکشنری، تا
# این دو هرگز از هم دور نیفتند (درس تصمیم ۴۳: پرامپتی که چیز غیرمجاز را مجاز بداند،
# مدل را بی‌نهایت به همان اشتباه می‌کشاند).
FUNCTIONS: dict[str, tuple[type, ...]] = {
    # تجمیعی
    "COUNT": (exp.Count,), "SUM": (exp.Sum,), "AVG": (exp.Avg,), "MIN": (exp.Min,), "MAX": (exp.Max,),
    "STDDEV": (exp.Stddev,), "STDDEV_POP": (exp.StddevPop,), "STDDEV_SAMP": (exp.StddevSamp,),
    # `VAR_POP` عمداً نیست: sqlglot آن را `VARIANCE_POP` بازتولید می‌کند که در MySQL وجود
    # ندارد (آزمون «روی MySQL واقعی اجرا می‌شود» پیدایش کرد).
    "VARIANCE": (exp.Variance,), "VAR_SAMP": (exp.Variance,),
    # ریاضی
    "ABS": (exp.Abs,), "ROUND": (exp.Round,), "FLOOR": (exp.Floor,), "CEIL": (exp.Ceil,),
    "CEILING": (exp.Ceil,), "SQRT": (exp.Sqrt,), "POW": (exp.Pow,), "POWER": (exp.Pow,),
    "EXP": (exp.Exp,), "LN": (exp.Ln,), "LOG": (exp.Ln,), "LOG10": (exp.Log,),
    "MOD": (exp.Mod,), "SIGN": (exp.Sign,), "GREATEST": (exp.Greatest,), "LEAST": (exp.Least,),
    # شرطی و تبدیل
    "IF": (exp.If,), "IFNULL": (exp.Coalesce,), "COALESCE": (exp.Coalesce,), "NULLIF": (exp.Nullif,),
    "CAST": (exp.Cast,), "CONVERT": (exp.Cast,),
    # تاریخ و زمان
    "YEAR": (exp.Year, exp.TsOrDsToDate), "MONTH": (exp.Month, exp.TsOrDsToDate),
    "DAY": (exp.Day, exp.TsOrDsToDate), "HOUR": (exp.Hour,), "MINUTE": (exp.Minute,),
    "SECOND": (exp.Second,), "DATE": (exp.TsOrDsToDate,), "EXTRACT": (exp.Extract,),
    "DATE_FORMAT": (exp.TimeToStr, exp.TsOrDsToTimestamp), "FROM_UNIXTIME": (exp.UnixToTime,),
    "DATE_ADD": (exp.DateAdd,), "DATE_SUB": (exp.DateSub,), "DATEDIFF": (exp.DateDiff,),
    "TIMESTAMPDIFF": (exp.TimestampDiff,), "CURDATE": (exp.CurrentDate,),
    # متن
    "CONCAT": (exp.Concat,), "LOWER": (exp.Lower,), "UPPER": (exp.Upper,),
    "SUBSTRING": (exp.Substring,), "LENGTH": (exp.Length,), "TRIM": (exp.Trim,),
}

# تابع‌هایی که sqlglot نمی‌شناسد و به‌صورت `Anonymous` می‌آیند. فقط همین نام‌ها مجازند.
ANONYMOUS_FUNCTIONS = frozenset({"UNIX_TIMESTAMP", "NOW"})
FUNCTIONS_DISPLAY = tuple(sorted(set(FUNCTIONS) | ANONYMOUS_FUNCTIONS))

# ساختار: جمله، شرط، مرتب‌سازی، حساب، و نوع‌ها. `Subquery`، `Join`، `Union`، `With`،
# `Window`، `Into`، `Lock`، `Hint` و `Parameter` عمداً نیستند.
_STRUCTURE_NAMES = (
    "Select", "From", "Table", "TableAlias", "Where", "Group", "Having", "Order", "Ordered",
    "Limit", "Offset", "Distinct", "Alias", "Column", "Identifier", "Star", "Literal", "Null",
    "Boolean", "Paren", "And", "Or", "Not", "Xor", "EQ", "NEQ", "GT", "GTE", "LT", "LTE",
    "Between", "In", "Is", "Like", "Add", "Sub", "Mul", "Div", "IntDiv", "Mod", "Neg",
    "Case", "If", "DataType", "DataTypeParam", "Interval", "Var", "Concat",
)
STRUCTURE = frozenset(getattr(exp, name) for name in _STRUCTURE_NAMES)
ALLOWED_NODES = STRUCTURE | {cls for classes in FUNCTIONS.values() for cls in classes}

# ممنوع‌ها، هرکدام با دلیل — تا پیام رد مبهم نماند، و تا پرامپت همین فهرست را نقل کند.
FORBIDDEN_REASONS = {
    "SLEEP": "سرور را معطل می‌کند (حمله‌ی منع سرویس)",
    "BENCHMARK": "پردازنده‌ی سرور را مصرف می‌کند (حمله‌ی منع سرویس)",
    "LOAD_FILE": "فایل روی سرور دیتابیس را می‌خواند",
    "GET_LOCK": "قفل نشست می‌گیرد و منابع را نگه می‌دارد",
    "INTO": "خروجی را در فایل یا متغیر می‌نویسد",
    "FOR UPDATE": "ردیف‌ها را قفل می‌کند",
    "LOCK IN SHARE MODE": "ردیف‌ها را قفل می‌کند",
    "JOIN": "نسخه‌ی اول فقط یک جدول را می‌خواند",
    "UNION": "نسخه‌ی اول فقط یک جدول را می‌خواند",
    "subquery": "نسخه‌ی اول فقط یک جدول را می‌خواند",
    "WITH": "نسخه‌ی اول فقط یک جدول را می‌خواند",
    "window function": "نسخه‌ی اول پشتیبانی نمی‌کند",
    "@variable": "متغیر سیستمی و کاربر پیکربندی را افشا یا نشست را عوض می‌کند",
    "optimizer hint": "می‌تواند متغیر نشست را عوض کند",
}
FORBIDDEN = frozenset(FORBIDDEN_REASONS)

# گره‌ی ممنوعی که کلید دلیلش فرق دارد.
_NODE_REASON = {
    exp.Join: "JOIN", exp.Union: "UNION", exp.Intersect: "UNION", exp.Except: "UNION",
    exp.Subquery: "subquery", exp.With: "WITH", exp.CTE: "WITH", exp.Window: "window function",
    exp.Into: "INTO", exp.Parameter: "@variable", exp.SessionParameter: "@variable",
    exp.Hint: "optimizer hint",
}

_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _reject(reason: str) -> Result:
    return Result(ok=False, query=None, reason=reason)


def _why_node(node: exp.Expression) -> str:
    """پیام رد برای یک گره‌ی بیرون از فهرست سفید."""
    if isinstance(node, exp.Lock):
        key = "FOR UPDATE" if node.args.get("update") else "LOCK IN SHARE MODE"
        return f"«{key}» ممنوع است: {FORBIDDEN_REASONS[key]}."
    for kind, key in _NODE_REASON.items():
        if isinstance(node, kind):
            return f"«{key}» ممنوع است: {FORBIDDEN_REASONS[key]}."
    if isinstance(node, exp.Anonymous):
        name = str(node.name).upper()
        if name in FORBIDDEN_REASONS:
            return f"تابع «{name}» ممنوع است: {FORBIDDEN_REASONS[name]}."
        return f"تابع «{name}» در فهرست مجاز نیست."
    return f"ساختار «{type(node).__name__}» در فهرست مجاز نیست."


def _scan(tree: exp.Expression) -> str | None:
    """اولین گره‌ی بیرون از فهرست سفید را پیدا می‌کند و دلیلش را برمی‌گرداند."""
    for node in tree.walk():
        if isinstance(node, exp.Anonymous):
            if str(node.name).upper() not in ANONYMOUS_FUNCTIONS:
                return _why_node(node)
        elif type(node) not in ALLOWED_NODES:
            return _why_node(node)
    return None


def _check_table(tree: exp.Expression, source: str, allowed: set[str]) -> str | None:
    """دقیقاً یک جدول، بدون نام دیتابیس، در فهرست سفید، و همان که مدل به‌عنوان `table` گفته."""
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1:
        return "کوئری باید دقیقاً یک جدول را بخواند (FROM)."
    table = tables[0]
    if table.args.get("db") or table.args.get("catalog"):
        return "نام جدول نباید با نام دیتابیس بیاید."
    name = table.name
    if name not in allowed:
        return f"جدول «{name}» جزو جدول‌های مجاز نیست."
    if name != source:
        return f"جدولِ داخل SQL («{name}») با جدولِ اعلام‌شده («{source}») یکی نیست."
    return None


def _parse(sql: str) -> exp.Expression | str:
    """درخت نحوی، یا پیام رد. هرگز استثنا نمی‌دهد: پارسر روی متنِ دلخواه ممکن است هر خطایی بدهد."""
    try:
        trees = [tree for tree in sqlglot.parse(sql, dialect=DIALECT) if tree is not None]
    except Exception:  # noqa: BLE001 — ورودی دلخواهِ مدل است؛ نوع خطای پارسر مهم نیست، رد شدنش مهم است
        return "SQL قابل‌خواندن نیست."
    if len(trees) != 1:
        return "فقط یک دستور مجاز است."
    if type(trees[0]) is not exp.Select:
        return "فقط SELECT مجاز است."
    return trees[0]


def _apply_limits(tree: exp.Select, row_filter: dict | None) -> str | None:
    """شرط سطری را کنار WHERE می‌چسباند و LIMIT را به سقف می‌رساند."""
    for field, value in (row_filter or {}).items():
        if not isinstance(field, str) or not _FIELD.match(field) or not isinstance(value, (str, int, float, bool)):
            return "شرط سطری نامعتبر است."
        condition = exp.EQ(this=exp.column(field), expression=exp.convert(value))
        where = tree.args.get("where")
        combined = exp.And(this=condition, expression=exp.Paren(this=where.this)) if where else condition
        tree.set("where", exp.Where(this=combined))

    max_rows = config.settings.max_rows
    if max_rows is not None:
        limit = tree.args.get("limit")
        current = limit.expression if limit else None
        if not (isinstance(current, exp.Literal) and current.is_int and int(current.name) <= max_rows):
            tree.limit(max_rows, copy=False)
    return None


def check(query: Any, source: Any, allowed_sources: set[str], row_filter: dict | None = None) -> Result:
    """بازبینی یک SQL پیش از اجرا. تنها راه رسیدن کوئری به دیتابیس. هرگز استثنا نمی‌دهد."""
    if not isinstance(source, str) or source not in allowed_sources:
        shown = source if isinstance(source, str) else type(source).__name__
        return _reject(f"جدول «{shown}» جزو جدول‌های مجاز نیست.")
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_SQL_CHARS:
        return _reject(f"کوئری باید یک متن SQL ناخالی و حداکثر {MAX_SQL_CHARS} نویسه باشد.")

    tree = _parse(query)
    if isinstance(tree, str):
        return _reject(tree)
    problem = _scan(tree) or _check_table(tree, source, allowed_sources) or _apply_limits(tree, row_filter)
    if problem:
        return _reject(problem)

    # چیزی که اجرا می‌شود SQLِ بازتولیدشده از درخت است، نه متن مدل؛ و آن هم دوباره
    # از همین بازبینی می‌گذرد.
    final = tree.sql(dialect=DIALECT, comments=False)
    again = _parse(final)
    if isinstance(again, str) or (_scan(again) or _check_table(again, source, allowed_sources)):
        return _reject("SQL بازتولیدشده از بازبینی نگذشت.")
    return Result(ok=True, query=final, reason="", max_time_ms=config.settings.query_timeout_ms)
