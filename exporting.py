"""تبدیل ردیف‌های Answer به فایل‌های CSV و Excel."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from openpyxl import Workbook

import config

# نام قابلیت در پروفایل مشتری، به‌ازای هر نوع خروجی. اینجا می‌نشیند نه در
# `ask.py` و `api/main.py`، وگرنه دو لایه‌ی نمایش هرکدام نسخه‌ی خودشان را
# می‌داشتند و روزی یکی از هم دور می‌افتاد (قاعده‌ی امنیتی ۴).
CAPABILITIES = {"csv": "export_csv", "excel": "export_excel"}


def is_enabled(kind: str) -> bool:
    """آیا پروفایل مشتری این نوع خروجی را دارد."""
    return CAPABILITIES[kind] in config.settings.customer.capabilities


# کاراکترهایی که Excel و LibreOffice آغاز یک **فرمول** می‌دانند.
_FORMULA_STARTERS = ("=", "+", "-", "@", "\t", "\r")


def _safe(value):
    """سلولی که در Excel به فرمول تبدیل می‌شود را به متن ساده برمی‌گرداند.

    متن داخل داکیومنت‌های دیتابیس غیرقابل‌اعتماد است (بخش ۴ نقشه، تزریق
    غیرمستقیم). اگر سلولی با `=` شروع شود، Excel موقع باز کردن فایل آن را
    *اجرا* می‌کند — یعنی محتوای دیتابیس مشتری روی کامپیوتر کسی که فایل را باز
    می‌کند فرمان می‌شود. یک آپستروف ابتدای سلول، Excel را وادار می‌کند آن را
    متن ببیند.

    فقط روی **رشته** اعمال می‌شود، نه عدد: `-27.31` یک عدد منفی است نه فرمول،
    و تبدیلش به متن یعنی خراب‌کردن همان چیزی که کاربر می‌خواست.
    """
    if isinstance(value, str) and value.startswith(_FORMULA_STARTERS):
        return "'" + value
    return value


def _columns(rows: list[dict]) -> list[str]:
    return list(dict.fromkeys(key for row in rows for key in row))


def to_csv(rows: list[dict]) -> str:
    """همه‌ی ستون‌های نتیجه را به CSV قابل ذخیره تبدیل می‌کند."""
    columns = _columns(rows)
    if not columns:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows({column: _safe(row.get(column, "")) for column in columns}
                     for row in rows)
    return buffer.getvalue()


def to_excel(rows: list[dict]) -> bytes:
    """نتیجه را به یک فایل Excel در حافظه تبدیل می‌کند."""
    workbook = Workbook()
    sheet = workbook.active
    columns = _columns(rows)
    if columns:
        sheet.append(columns)
        for row in rows:
            sheet.append([_safe(row.get(column, "")) for column in columns])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def write_csv(rows: list[dict], path: Path) -> None:
    """CSV را در مسیر انتخاب‌شده‌ی کاربر می‌نویسد."""
    path.write_text(to_csv(rows), encoding="utf-8", newline="")


def write_excel(rows: list[dict], path: Path) -> None:
    """Excel را در مسیر انتخاب‌شده‌ی کاربر می‌نویسد."""
    path.write_bytes(to_excel(rows))
