"""`Answer`: آنچه به کاربر برمی‌گردد.

جدا از گراف است چون لایه‌های نمایش (خط فرمان و API) و صادرات فقط همین را می‌شناسند
و لازم نیست برای دیدن آن کل گراف و ایجنت‌ها import شوند.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Answer:
    """آنچه به کاربر برمی‌گردد. لایه‌ی نمایش فقط همین را سریالایز می‌کند.

    تفکیک `message` از `error` عمدی است: «این داده در دیتابیس نیست» خطا نیست،
    یک جواب معتبر است و باید متفاوت نمایش داده شود. قاطی‌کردنشان اشتباه
    نسخه‌ی ۱ بود (docs/v1-reference.md بخش ۴).
    """

    question: str
    # کالکشن یا جدولی که کوئری رویش اجرا شد، و خودِ کوئری (فهرست stage برای
    # مونگو، متن برای SQL). نام‌ها عمومی‌اند چون `Answer` مال هسته است.
    source: str | None = None
    query: Any = None
    rows: list[dict] = field(default_factory=list)
    summary: str | None = None
    chart: dict[str, Any] | None = None
    # آیا جواب بعد از یک بار اصلاح به دست آمد. برای کاربر یعنی «این جواب
    # ارزان به دست نیامد»، و برای ما نشانه‌ای که پرامپت جای بهترشدن دارد.
    repaired: bool = False
    message: str | None = None
    error: str | None = None
