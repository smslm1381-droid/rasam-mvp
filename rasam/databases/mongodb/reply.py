"""خواندن پاسخ مدل برای MongoDB.

شکل خروجی مدل را پرامپت هر دیتابیس تعیین می‌کند: مونگو یک شیء JSON با کلیدهای
`collection` و `pipeline` می‌خواهد. پس خواندنش هم مال همین پوشه است، نه هسته.
(کلیدهای JSON عوض نمی‌شوند: تغییرشان رفتار مدل را عوض می‌کند.)
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
    return Reply(source=parsed.get("collection"), query=parsed.get("pipeline"))
