"""تشخیص درخواست نمودار و اعتبارسنجی مشخصات پیشنهادی مدل."""

from __future__ import annotations

import json
import math
from typing import Any

import prompts

CHART_WORDS = ("نمودار", "رسم", "چارت", "گراف")
CHART_TYPES = {"line", "bar", "scatter", "area"}
MAX_TITLE_CHARS = 120


def wants_chart(question: str) -> bool:
    """فقط با خواست صریح کاربر مسیر نمودار را فعال می‌کند."""
    return any(word in question for word in CHART_WORDS)


def numeric_columns(rows: list[dict]) -> list[str]:
    """نام ستون‌هایی را می‌دهد که دست‌کم یک مقدار عددی معتبر دارند."""
    columns = []
    for column in dict.fromkeys(key for row in rows for key in row):
        values = (row.get(column) for row in rows)
        if any(isinstance(value, (int, float)) and not isinstance(value, bool)
               and math.isfinite(value) for value in values):
            columns.append(column)
    return columns


def local_check(rows: list[dict]) -> tuple[bool, str | None]:
    """پیش از تماس با مدل، امکان معنادار بودن نمودار را بررسی می‌کند."""
    if len(rows) < 2:
        return False, "نتیجه برای رسم نمودار دست‌کم به دو ردیف نیاز دارد."
    if not numeric_columns(rows):
        return False, "نتیجه ستون عددی برای رسم نمودار ندارد."
    return True, None


def build_prompt(question: str, rows: list[dict]) -> str:
    """پرامپت مشخصات نمودار را با ستون‌های واقعی نتیجه می‌سازد."""
    columns = list(dict.fromkeys(key for row in rows for key in row))
    return prompts.build_chart_prompt(question, columns, rows)


def parse_and_validate(text: str, rows: list[dict]) -> dict[str, Any] | None:
    """JSON مدل را به مشخصات نمودار محدود به نتیجه‌ی واقعی تبدیل می‌کند."""
    try:
        candidate = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(candidate, dict) or not candidate.get("feasible"):
        return None

    columns = set(key for row in rows for key in row)
    numeric = set(numeric_columns(rows))
    y = [column for column in candidate.get("y", []) if column in numeric]
    x = candidate.get("x") if candidate.get("x") in columns else None
    if x in y:
        x = None
    if not y:
        return None
    title = str(candidate.get("title") or "نمودار نتیجه")[:MAX_TITLE_CHARS]
    chart_type = candidate.get("chart_type")
    return {
        "chart_type": chart_type if chart_type in CHART_TYPES else "bar",
        "x": x,
        "y": y,
        "title": title,
    }
