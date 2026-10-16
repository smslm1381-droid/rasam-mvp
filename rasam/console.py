"""کنسول و فایل‌های متنی، آن‌طور که ویندوز لازم دارد.

دو مشکل واقعی ویندوز که روی مک دیده نمی‌شود:

۱. **خروجی کنسول.** پایتون روی ویندوز با کدگذاری کنسول (`cp1252` یا `cp1256`) چاپ
   می‌کند. چاپ فارسی یا ✅ آنجا `UnicodeEncodeError` می‌دهد و برنامه وسط جواب
   می‌افتد. `use_utf8()` خروجی را UTF-8 می‌کند؛ اگر ترمینال نتواند نشان بدهد، به‌جای
   افتادن یک نویسه‌ی جایگزین می‌گذارد. (برای نمایش درست فارسی، Windows Terminal بهتر
   از `cmd` قدیمی است.)
۲. **BOM.** Notepad و بعضی ویرایشگرهای ویندوز فایل UTF-8 را با یک نویسه‌ی نامرئی در
   ابتدا (BOM) ذخیره می‌کنند. PyYAML با آن می‌افتد (پروفایل مشتری، سوالات طلایی) و
   مستندات یک نویسه‌ی نامرئی در ابتدا می‌گیرند. `read_text()` با `utf-8-sig` می‌خواند،
   که فایل بدون BOM را هم همان‌طور درست می‌خواند. (`.env` نیاز ندارد: python-dotenv
   خودش BOM را برمی‌دارد — در تست سنجیده شد، حدس نبود.)
"""

from __future__ import annotations

import sys
from pathlib import Path


def use_utf8() -> None:
    """stdin و stdout و stderr را UTF-8 می‌کند. روی مک و لینوکس که از قبل UTF-8‌اند بی‌اثر است.

    ورودی هم لازم است: وقتی پاسخ‌های `onboard.py` از یک لوله می‌آیند (یا یک نام فارسی
    تایپ می‌شود)، ویندوز با کدگذاری محلی می‌خواند و حروف به‌هم‌ریخته می‌رسند.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:  # جریانی که pytest یا ابزار دیگر جایش گذاشته ممکن است نداشته باشد
            reconfigure(encoding="utf-8", errors="replace")


def read_text(path: Path) -> str:
    """فایل متنیِ قابل‌ویرایش توسط انسان (پروفایل، دانش، سوالات طلایی) را می‌خواند."""
    return path.read_text(encoding="utf-8-sig")
