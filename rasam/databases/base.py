"""قرارداد مشترک همه‌ی دیتابیس‌ها.

هر نوع دیتابیس یک پوشه در `rasam/databases/` دارد (`mongodb/`، `postgresql/`، …)
و یک کلاس که این قرارداد را پیاده می‌کند. گراف (`rasam/core/graph.py`) فقط با
همین قرارداد حرف می‌زند و نمی‌داند پشتش مونگوست یا SQL.

افزودن دیتابیس تازه یعنی: یک پوشه‌ی تازه کنار بقیه، و یک خط در `registry.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Result:
    """نتیجه‌ی بازبینی — یک *مقدار*، نه استثنا (قاعده‌ی امنیتی ۷).

    در حالت رد، `pipeline` برابر `None` است. این عمدی است: اگر جایی از کد
    یادش رفت `ok` را چک کند، بلافاصله می‌شکند به‌جای اینکه یک کوئری
    اعتبارسنجی‌نشده را اجرا کند (تصمیم ۷ نقشه).
    """

    ok: bool
    pipeline: list[dict] | None
    reason: str
    # سقف زمان همراه نتیجه می‌آید تا فراخوان نتواند فراموشش کند. گارد تنها
    # جایی است که همه‌ی کوئری‌ها از آن رد می‌شوند، پس همه‌ی سقف‌ها باید از
    # همین‌جا بیرون بیایند.
    max_time_ms: int = 0


class DatabaseAgent(Protocol):
    db_type: str

    def describe_schema(self) -> str: ...

    def build_query_prompt(self, schema: str, question: str, collections: set[str],
                           failure: tuple[Any, str] | None = None,
                           want_chart: bool = False,
                           documentation: str | None = None,
                           examples: str | None = None) -> str: ...

    def validate_query(self, collection: str, query: Any) -> Result: ...

    def execute(self, collection: str, query: Any, max_time_ms: int) -> list[dict]: ...
