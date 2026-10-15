"""رشته‌ای که خودش را در خروجی تست‌ها نشان نمی‌دهد.

وقتی یک تست می‌شکند، pytest مقدار آرگومان‌های fixture را چاپ می‌کند. رشته‌ی اتصال
یک رمز دارد (حتی اگر فقط برای Docker محلی باشد) و نباید در ترمینال یا لاگ CI بنشیند.
`Secret` یک `str` معمولی است که فقط `repr`اش `'***'` است.
"""

from __future__ import annotations


class Secret(str):
    def __repr__(self) -> str:
        return "'***'"
