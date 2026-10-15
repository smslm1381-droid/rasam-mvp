"""خواندن پاسخ مدل برای MySQL.

مدل یک شیء JSON با دو کلید می‌دهد: `table` و `sql`. (برای مونگو `collection` و
`pipeline` است؛ شکل پاسخ را پرامپت هر دیتابیس تعیین می‌کند.) استخراج شیء از دل
متن مدل مشترک است (`databases/json_reply.py`).
"""

from __future__ import annotations

from rasam.databases.base import Reply
from rasam.databases.json_reply import split_json


def parse_reply(text: str) -> Reply:
    """پاسخ مدل را به `Reply` تبدیل می‌کند: کوئری، جمله‌ی فارسی، یا خطا."""
    parsed, message, error = split_json(text)
    if error:
        return Reply(error=error)
    if parsed is None:
        return Reply(message=message)
    return Reply(source=parsed.get("table"), query=parsed.get("sql"))
