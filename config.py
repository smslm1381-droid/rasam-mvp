"""تنظیمات رصام — تنها جایی که پروژه با محیط اجرا حرف می‌زند.

چرا یک فایل و یک نمونه: قاعده‌ی «هیچ مسیر، کلید یا نام مدلی hard-code نمی‌شود»
فقط وقتی قابل نگهداری است که یک در ورودی داشته باشد. بقیه‌ی کد به‌جای
`os.environ` از `config.settings` استفاده می‌کند؛ اگر روزی منبع تنظیمات عوض
شد (Vault، کانفیگ‌سرور، …) فقط همین فایل تغییر می‌کند.

چرا dataclass و نه pydantic: تنظیمات چند رشته و عدد ساده است. pydantic در این
پروژه برای `Answer` و State نگه داشته شده (بخش ۵ نقشه).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, fields
from pathlib import Path

from dotenv import load_dotenv

# ریشه‌ی پروژه از محل همین فایل استنتاج می‌شود، نه از دایرکتوری جاری، تا
# اجرای دستورها از هر جایی یک نتیجه بدهد.
PROJECT_ROOT = Path(__file__).resolve().parent

# override=False یعنی متغیر واقعیِ محیط سیستم بر فایل `.env` اولویت دارد؛
# رفتار درستِ استقرار روی سرور، جایی که `.env` وجود ندارد.
load_dotenv(PROJECT_ROOT / ".env", override=False)

ENV_PREFIX = "RASAM_"

# اینها پیش‌فرض ندارند: یا رازند یا مخصوص همین ماشین. نبودشان باید سر و صدا
# کند، نه اینکه با یک مقدار حدسی جای اشتباهی وصل شویم.
REQUIRED = (
    "MONGO_URI",
    "MONGO_DB",
    "CSV_DIR",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
)

_TRUE_VALUES = {"1", "true", "yes", "on"}


class ConfigError(Exception):
    """تنظیمات قابل خواندن نیست.

    این تنها جای پروژه است که استثنا پرتاب می‌شود و درست است: بدون تنظیمات
    هیچ‌چیز نمی‌تواند شروع شود، پس «خطا به‌عنوان مقدار» چیزی برای برگرداندن
    ندارد. قاعده‌ی ۷ (بخش ۴ نقشه) درباره‌ی مسیر پاسخ‌دادن به سوال است.
    """


def _env(name: str) -> str | None:
    """مقدار متغیر با پیشوند پروژه؛ رشته‌ی خالی مثل نبودن حساب می‌شود."""
    value = os.getenv(ENV_PREFIX + name)
    return value.strip() if value and value.strip() else None


def _number(name: str, default, convert, kind: str):
    raw = _env(name)
    if raw is None:
        return default
    try:
        return convert(raw)
    except ValueError:
        raise ConfigError(
            f"مقدار {ENV_PREFIX}{name} باید {kind} باشد، ولی «{raw}» است."
        ) from None


def _flag(name: str, default: bool) -> bool:
    raw = _env(name)
    return default if raw is None else raw.lower() in _TRUE_VALUES


def _hide_password(uri: str) -> str:
    """رمز داخل رشته‌ی اتصال را می‌پوشاند تا در ترمینال و لاگ دیده نشود."""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", uri)


@dataclass(frozen=True, repr=False)
class Settings:
    mongo_uri: str
    mongo_db: str
    # فقط اسکریپت seed این را می‌خواهد. اجباری‌کردنش یعنی مسیر عادیِ پاسخ به
    # سوال هم بدون یک اتصالِ نویسنده بالا نیاید — برعکس قاعده‌ی امنیتی ۲.
    mongo_admin_uri: str | None
    csv_dir: Path
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_max_tokens: int
    llm_temperature: float
    llm_disable_reasoning: bool
    verbose: bool

    def __repr__(self) -> str:
        """نمایش چندخطی و بی‌راز.

        چاپ تنظیمات اولین کاری است که آدم موقع عیب‌یابی می‌کند، پس نباید
        کلید و رمز را روی صفحه بریزد.
        """
        lines = []
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "llm_api_key":
                value = "***"
            elif field.name in ("mongo_uri", "mongo_admin_uri") and value:
                value = _hide_password(value)
            lines.append(f"  {field.name} = {value!r}")
        return "Settings(\n" + "\n".join(lines) + "\n)"


def _load() -> Settings:
    missing = [ENV_PREFIX + name for name in REQUIRED if _env(name) is None]
    if missing:
        raise ConfigError(
            "تنظیمات ناقص است. این متغیرها در فایل `.env` نیستند یا خالی‌اند:\n"
            + "\n".join(f"  - {name}" for name in missing)
            + "\n\nراه‌حل: فایل `.env.example` را به `.env` کپی کنید و مقادیرش را پر کنید."
        )

    csv_dir = Path(_env("CSV_DIR"))
    return Settings(
        mongo_uri=_env("MONGO_URI"),
        mongo_db=_env("MONGO_DB"),
        mongo_admin_uri=_env("MONGO_ADMIN_URI"),
        # مسیر نسبی نسبت به ریشه‌ی پروژه معنا می‌شود، نه دایرکتوری جاری.
        csv_dir=csv_dir if csv_dir.is_absolute() else (PROJECT_ROOT / csv_dir).resolve(),
        llm_api_key=_env("LLM_API_KEY"),
        llm_base_url=_env("LLM_BASE_URL"),
        llm_model=_env("LLM_MODEL"),
        # پیش‌فرض‌ها حاصل تجربه‌ی نسخه‌ی ۱‌اند (docs/v1-reference.md بخش ۵).
        llm_max_tokens=_number("LLM_MAX_TOKENS", 1024, int, "عدد صحیح"),
        llm_temperature=_number("LLM_TEMPERATURE", 0.1, float, "عدد اعشاری"),
        llm_disable_reasoning=_flag("LLM_DISABLE_REASONING", True),
        verbose=_flag("VERBOSE", False),
    )


settings = _load()
