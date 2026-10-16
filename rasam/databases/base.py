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

    `query` کوئریِ پذیرفته‌شده است؛ شکلش را فقط ایجنت همان دیتابیس می‌شناسد
    (برای مونگو فهرست stageها، برای SQL یک متن).

    در حالت رد، `query` برابر `None` است. این عمدی است: اگر جایی از کد یادش
    رفت `ok` را چک کند، بلافاصله می‌شکند به‌جای اینکه یک کوئری
    اعتبارسنجی‌نشده را اجرا کند (تصمیم ۷ نقشه).
    """

    ok: bool
    query: Any
    reason: str
    # سقف زمان همراه نتیجه می‌آید تا فراخوان نتواند فراموشش کند. گارد تنها
    # جایی است که همه‌ی کوئری‌ها از آن رد می‌شوند، پس همه‌ی سقف‌ها باید از
    # همین‌جا بیرون بیایند.
    max_time_ms: int = 0


@dataclass(frozen=True)
class Reply:
    """پاسخ مدل بعد از خواندن: دقیقاً یکی از سه حالت.

    - `source` و `query`: مدل کوئری ساخته (`source` کالکشن یا جدول است)
    - `message`: مدل جمله‌ای فارسی داده، یعنی سوال از این داده قابل جواب نیست
    - `error`: چیزی شبیه کوئری بود ولی خوانده نشد
    """

    source: str | None = None
    query: Any = None
    message: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class AccessReport:
    """نتیجه‌ی بررسی «کاربر دیتابیس واقعاً فقط-خواندنی است؟»."""

    read_only: bool
    detail: str


class DatabaseAgent(Protocol):
    db_type: str

    @staticmethod
    def connection_fields() -> list[dict]: ...

    @staticmethod
    def build_connection_uri(values: dict[str, str]) -> str: ...

    @staticmethod
    def test_connection(uri: str, database: str): ...

    def describe_schema(self) -> str: ...

    def list_sources(self) -> list[str]:
        """همه‌ی کالکشن‌ها یا جدول‌های دیتابیس — **نه** فقط مجازها.

        برای ابزار تحویل است: وقتی مشتری تازه می‌آید هنوز فهرست سفیدی نیست و
        انسان باید از میان این فهرست انتخاب کند. مسیر پاسخ به سوال هرگز آن را
        صدا نمی‌زند.
        """
        ...

    def check_read_only(self) -> AccessReport:
        """از روی **فهرست دسترسی‌های** کاربر می‌گوید فقط-خواندنی است یا نه.

        هرگز با امتحان نوشتن (تصمیم ۶۷): روی دیتابیس مشتریِ واقعی، اگر کاربر
        اشتباهاً دسترسی نوشتن داشته باشد، همان امتحان واقعاً می‌نویسد.
        """
        ...

    def list_fields(self, source: str) -> list[str]:
        """نام فیلدها یا ستون‌های یک منبع، برای پیش‌نویس مستندات مشتری."""
        ...

    def build_query_prompt(self, schema: str, question: str, sources: set[str],
                           failure: tuple[Any, str] | None = None,
                           want_chart: bool = False,
                           documentation: str | None = None,
                           examples: str | None = None) -> str: ...

    def format_example(self, example: dict) -> str:
        """یک نمونه‌ی `{question, why, source, query}` را به متن پرامپت تبدیل می‌کند."""
        ...

    def parse_reply(self, text: str) -> Reply: ...

    def validate_query(self, source: str, query: Any,
                       row_filter: dict[str, Any] | None = None) -> Result:
        """گارد. `row_filter` شرط اجباری سطح-ردیف است (`{فیلد: مقدار}`، برابری).

        ایجنت آن را به زبان خودش به **ابتدای** کوئری تزریق می‌کند تا هیچ بخش
        بعدی نتواند دورش بزند. گراف فعلاً همیشه `None` می‌دهد؛ مصرف‌کننده‌ی
        واقعی‌اش کنترل دسترسی سطری است و آزمون انطباق آن را پر می‌کند.
        """
        ...

    def execute(self, source: str, checked: Result) -> list[dict]:
        """فقط نتیجه‌ی **پذیرفته‌شده‌ی** گارد را می‌پذیرد، نه کوئری خام (قاعده‌ی ۳)."""
        ...
