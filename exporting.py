"""تبدیل ردیف‌های Answer به فایل‌های CSV و Excel."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from openpyxl import Workbook


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
    writer.writerows({column: row.get(column, "") for column in columns} for row in rows)
    return buffer.getvalue()


def to_excel(rows: list[dict]) -> bytes:
    """نتیجه را به یک فایل Excel در حافظه تبدیل می‌کند."""
    workbook = Workbook()
    sheet = workbook.active
    columns = _columns(rows)
    if columns:
        sheet.append(columns)
        for row in rows:
            sheet.append([row.get(column, "") for column in columns])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def write_csv(rows: list[dict], path: Path) -> None:
    """CSV را در مسیر انتخاب‌شده‌ی کاربر می‌نویسد."""
    path.write_text(to_csv(rows), encoding="utf-8", newline="")


def write_excel(rows: list[dict], path: Path) -> None:
    """Excel را در مسیر انتخاب‌شده‌ی کاربر می‌نویسد."""
    path.write_bytes(to_excel(rows))