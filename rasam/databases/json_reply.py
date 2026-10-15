"""خواندن مشترکِ پاسخ JSON مدل، برای آداپتورهایی که مدل را به JSON وا می‌دارند.

تا وقتی فقط مونگو بود، این کد داخل `mongodb/reply.py` بود. MySQL مصرف‌کننده‌ی
دوم است و (قاعده‌ی «انتزاع فقط وقتی دومین مورد آمد») بیرونش می‌کشد. آنچه مشترک
است **استخراج شیء JSON از دل متن مدل** است؛ اینکه کلیدهایش چیست (`collection` و
`pipeline` برای مونگو، `table` و `sql` برای MySQL) مال هر آداپتور می‌ماند.
"""

from __future__ import annotations

import json
import re

# نشانه‌ی اینکه مدل *قصد* کوئری داشته، حتی اگر نتیجه JSON معتبری نباشد.
_JSON_START = ("{", "[")

_BROKEN_JSON = (
    "مدل چیزی شبیه کوئری برگرداند که JSON معتبری نبود. "
    "دوباره بپرسید؛ اگر تکرار شد، مدل تنظیم‌شده در RASAM_LLM_MODEL را عوض کنید."
)


def _balanced_object(text: str) -> str | None:
    """از اولین `{`، تا آکولادِ متناظرش را برمی‌گرداند.

    چرا لازم شد: بعضی مدل‌ها بعد از شیء JSON چیز اضافه می‌گذارند — یک `}`
    زیادی، یک جمله‌ی توضیح، یا متن فکرکردنشان. `json.loads` روی کل متن شکست
    می‌خورد و یک کوئریِ کاملاً درست دور ریخته می‌شود.

    این *حدس زدن* نیست: فقط آکولادها شمرده می‌شوند و رشته‌های داخل JSON (که
    ممکن است خودشان آکولاد داشته باشند) رد می‌شوند. چیزی که برمی‌گردد باز هم
    باید از `json.loads` و بعد از گارد رد شود.
    """
    start = text.find("{")
    if start < 0:
        return None

    depth, in_string, escaped = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def split_json(text: str) -> tuple[dict | None, str | None, str | None]:
    """خروجی خام مدل را سه‌راهی تفکیک می‌کند: شیء JSON، جمله‌ی فارسی، یا خطا.

    قاعده‌ی تشخیص از v1-reference بخش ۴: اگر JSON معتبر بود، تلاش برای کوئری
    بوده؛ وگرنه جمله‌ای است که طبق قاعده‌ی ۵ پرامپت داده شده.

    حالت سوم از یک شکست واقعی آمد: مدلی یک `}` اضافه در جواب گذاشت، JSON از هم
    پاشید، و آن متن به‌عنوان «جمله‌ی فارسی» پذیرفته شد — کاربر به‌جای جواب، یک
    خط JSON خام دید و برنامه آن را موفقیت شمرد. پس متنی که با `{` یا `[` شروع
    می‌شود هرگز جمله نیست: یا کوئری است یا خطا.

    بلوک markdown با اینکه قاعده‌ی ۶ منعش کرده پاک می‌شود، چون مدل‌ها گاهی
    اضافه‌اش می‌کنند و ردکردن یک کوئری سالم به‌خاطر سه بک‌تیک بی‌دلیل است.
    """
    stripped = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = _retry_as_object(stripped)
        if parsed is None:
            if stripped.startswith(_JSON_START):
                return None, None, _BROKEN_JSON
            return None, text, None
    if isinstance(parsed, dict):
        return parsed, None, None
    # JSON معتبر ولی نه یک شیء: مثلاً فقط pipeline بدون نام کالکشن.
    return None, None, _BROKEN_JSON


def _retry_as_object(text: str) -> dict | None:
    """تلاش دوم: فقط شیء JSON را از دل متن بیرون بکش و همان را بخوان."""
    candidate = _balanced_object(text)
    if candidate is None:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
