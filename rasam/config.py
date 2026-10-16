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
import sys
from dataclasses import dataclass, fields
from pathlib import Path

from dotenv import load_dotenv

from rasam import vault
from rasam.customer import CustomerProfile, load_profile
from rasam.errors import UserFacingError

# ریشه‌ی پروژه از محل همین فایل استنتاج می‌شود، نه از دایرکتوری جاری، تا
# اجرای دستورها از هر جایی یک نتیجه بدهد. این فایل در `rasam/` است، پس ریشه
# یک پوشه بالاتر است.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_MODE = os.getenv("RASAM_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"}


def _home_dir() -> Path:
    if raw := os.getenv("RASAM_HOME", "").strip():
        return Path(raw).expanduser().resolve()
    if not DESKTOP_MODE:
        return PROJECT_ROOT
    if sys.platform == "win32":
        return Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming") / "Rasam"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Rasam"
    return Path.home() / ".local" / "share" / "Rasam"


DATA_HOME = _home_dir()
CUSTOMERS_DIR = DATA_HOME / "customers"
CHROMA_DIR = DATA_HOME / "chroma"

# override=False یعنی متغیر واقعیِ محیط سیستم بر فایل `.env` اولویت دارد؛
# رفتار درستِ استقرار روی سرور، جایی که `.env` وجود ندارد.
# نصب رومیزی نباید تصادفی رازهای فایل توسعه را بخواند.
if not DESKTOP_MODE:
    load_dotenv(DATA_HOME / ".env", override=False, encoding="utf-8-sig")

ENV_PREFIX = "RASAM_"

# تعداد کل تلاش برای ساختن کوئری (اول + ترمیم) وقتی پروفایل چیزی نگفته باشد.
DEFAULT_MAX_ATTEMPTS = 2

# اینها پیش‌فرض ندارند: یا رازند یا مخصوص همین ماشین. نبودشان باید سر و صدا
# کند، نه اینکه با یک مقدار حدسی جای اشتباهی وصل شویم.
REQUIRED = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "CUSTOMER",
)

_TRUE_VALUES = {"1", "true", "yes", "on"}


class ConfigError(UserFacingError):
    """تنظیمات قابل خواندن نیست.

    این تنها جای پروژه است که استثنا پرتاب می‌شود و درست است: بدون تنظیمات
    هیچ‌چیز نمی‌تواند شروع شود، پس «خطا به‌عنوان مقدار» چیزی برای برگرداندن
    ندارد. قاعده‌ی ۷ (بخش ۴ نقشه) درباره‌ی مسیر پاسخ‌دادن به سوال است.
    """


def _env(name: str) -> str | None:
    """مقدار متغیر با پیشوند پروژه؛ رشته‌ی خالی مثل نبودن حساب می‌شود."""
    value = os.getenv(ENV_PREFIX + name)
    return value.strip() if value and value.strip() else None


def env_value(name: str) -> str | None:
    """مقدار یک متغیر با پیشوند پروژه، برای ابزارهایی که فقط وجودش را می‌پرسند."""
    return _env(name)


def secret_value(name: str) -> str | None:
    value = env_value(name)
    if value is not None:
        return value
    result = vault.read_secret(name)
    if not result.ok:
        raise ConfigError(f"خواندن راز {ENV_PREFIX}{name}: {result.error}")
    return result.value


def _required_value(name: str) -> str | None:
    return secret_value(name) if name == "LLM_API_KEY" else _env(name)


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


# کلمه‌ی مخصوصی که یعنی «اصلاً این پارامتر را نفرست». راه فرار برای سرویسی
# که `reasoning_effort` را نمی‌شناسد و با دیدنش خطا می‌دهد.
REASONING_UNSET = "unset"


def _reasoning_effort() -> str | None:
    """چقدر مدل پیش از جواب‌دادن «فکر» کند.

    پیش‌فرض `none` یعنی خاموش. برای تولید کوئری، فکرکردن فقط کند و گران است:
    روی Gemini 3 Flash اندازه‌گیری شد، ۳٫۴ ثانیه در برابر ۱٫۲ ثانیه با همان
    جواب. روشن‌کردنش در آینده یک کلمه است — `low`، `medium` یا `high`.

    مقدار عمداً اعتبارسنجی نمی‌شود: هر سرویسی ممکن است سطح تازه‌ای اضافه کند
    و فهرست بسته یعنی همان مشکلی که این تنظیم قرار بود حلش کند.
    """
    raw = _env("LLM_REASONING_EFFORT")
    if raw is None:
        return "none"
    return None if raw.lower() == REASONING_UNSET else raw


def _flag(name: str, default: bool) -> bool:
    raw = _env(name)
    return default if raw is None else raw.lower() in _TRUE_VALUES


def _hide_password(uri: str) -> str:
    """رمز داخل رشته‌ی اتصال را می‌پوشاند تا در ترمینال و لاگ دیده نشود."""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", uri)


@dataclass(frozen=True, repr=False)
class Settings:
    customer: CustomerProfile
    connection_uri: str
    # نام دیتابیس مال پروفایل مشتری است، نه `.env`: با یک پروسه به‌ازای هر
    # مشتری (تصمیم ۸۰) هر دو کار می‌کرد، ولی نامِ دیتابیس راز نیست و کنار بقیه‌ی
    # پیکربندی مشتری، در یک فایل قابل‌بازبینی، جایش درست‌تر است.
    database: str
    # فقط اسکریپت seed این را می‌خواهد. اجباری‌کردنش یعنی مسیر عادیِ پاسخ به
    # سوال هم بدون یک اتصالِ نویسنده بالا نیاید — برعکس قاعده‌ی امنیتی ۲.
    mongo_admin_uri: str | None
    # نام کالکشن مخصوص هر مشتری است، پس در کد نمی‌نشیند. گارد این فهرست را
    # می‌گیرد و هر کوئری بیرون از آن را رد می‌کند — دفاع در برابر کالکشن‌های
    # حساسِ خودِ همان مشتری، مثل `users` یا `billing`.
    allowed_sources: frozenset[str]
    # فقط اسکریپت seed دمو آن را می‌خواهد؛ مشتری واقعی CSV ندارد.
    csv_dir: Path | None
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    api_key: str | None
    # سقف‌های اجرای کوئری. گارد (قدم ۴) اعمالشان می‌کند.
    query_timeout_ms: int
    max_rows: int | None
    llm_timeout_ms: int
    llm_max_tokens: int
    llm_temperature: float
    llm_reasoning_effort: str | None
    max_question_chars: int
    max_result_rows: int
    max_result_chars: int
    max_knowledge_chars: int
    max_attempts: int
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
            elif field.name in ("connection_uri", "mongo_admin_uri") and value:
                value = _hide_password(value)
            lines.append(f"  {field.name} = {value!r}")
        return "Settings(\n" + "\n".join(lines) + "\n)"


def _require_env() -> None:
    missing = [ENV_PREFIX + name for name in REQUIRED if _required_value(name) is None]
    if missing:
        raise ConfigError(
            "تنظیمات ناقص است. این متغیرها در فایل `.env` نیستند یا خالی‌اند:\n"
            + "\n".join(f"  - {name}" for name in missing)
            + "\n\nراه‌حل: فایل `.env.example` را به `.env` کپی کنید و مقادیرش را پر کنید."
        )


def _csv_dir() -> Path | None:
    """مسیر CSVهای دمو، یا None. مسیر نسبی نسبت به ریشه‌ی پروژه معنا می‌شود، نه دایرکتوری جاری."""
    raw = _env("CSV_DIR")
    if raw is None:
        return None
    path = Path(raw)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _connection_uri(profile: CustomerProfile) -> str:
    uri = secret_value(profile.connection_env)
    if uri is None:
        raise ConfigError(
            f"تنظیمات ناقص است. متغیر {ENV_PREFIX}{profile.connection_env} "
            f"از پروفایل مشتری «{profile.name}» در محیط یا انبار امن رمز پیدا نشد."
        )
    return uri


def _load() -> Settings:
    _require_env()
    profile = load_profile(_env("CUSTOMER"), CUSTOMERS_DIR)
    return Settings(
        customer=profile,
        connection_uri=_connection_uri(profile),
        database=profile.database,
        mongo_admin_uri=_env("MONGO_ADMIN_URI"),
        allowed_sources=profile.allowed_sources,
        csv_dir=_csv_dir(),
        llm_api_key=secret_value("LLM_API_KEY"),
        llm_base_url=_env("LLM_BASE_URL"),
        llm_model=_env("LLM_MODEL"),
        api_key=_env("API_KEY"),
        # کندترین کوئری واقعیِ اندازه‌گیری‌شده ۰٫۰۶ ثانیه بود؛ ۶۰ ثانیه یعنی هیچ
        # سوال سالمی به سقف نمی‌خورد، ولی یک کوئری معیوب سرور را گروگان نمی‌گیرد.
        query_timeout_ms=_number("QUERY_TIMEOUT_MS", 60_000, int, "عدد صحیح"),
        # سقف‌های مشتری فقط از پروفایل می‌آیند: اگر `.env` هم یک نسخه داشت، «سقف روشن است؟»
        # دو جواب می‌داشت و بررسی آمادگی تحویل نمی‌توانست به هیچ‌کدام اعتماد کند.
        max_rows=profile.limits.get("max_rows"),
        # پیش‌فرض‌ها حاصل تجربه‌ی نسخه‌ی ۱‌اند (docs/v1-reference.md بخش ۵).
        # جواب‌های واقعی ۱ تا ۳ ثانیه طول می‌کشند. سقف برای حالتی است که
        # سرویس یا شبکه گیر کند و درخواست معلق بماند — از قدم ۱۳ که API
        # می‌آید، هر درخواست معلق یک اتصال سرور را اشغال نگه می‌دارد.
        llm_timeout_ms=_number("LLM_TIMEOUT_MS", 90_000, int, "عدد صحیح"),
        llm_max_tokens=_number("LLM_MAX_TOKENS", 1024, int, "عدد صحیح"),
        llm_temperature=_number("LLM_TEMPERATURE", 0.1, float, "عدد اعشاری"),
        llm_reasoning_effort=_reasoning_effort(),
        max_question_chars=_number("MAX_QUESTION_CHARS", 2000, int, "عدد صحیح"),
        max_result_rows=_number("MAX_RESULT_ROWS", 30, int, "عدد صحیح"),
        max_result_chars=_number("MAX_RESULT_CHARS", 4000, int, "عدد صحیح"),
        # بودجه‌ی دانش پرامپت (ساختار + مستندات + نمونه‌ها). زیر این عدد همه‌ی
        # دانش کامل فرستاده می‌شود؛ بالای آن، بازیابی معنایی کوتاهش می‌کند.
        # دانش مشتری دمو ۱۲٫۴ هزار کاراکتر است، پس این سقف دو برابر آن است.
        max_knowledge_chars=_number("MAX_KNOWLEDGE_CHARS", 24_000, int, "عدد صحیح"),
        max_attempts=profile.limits.get("max_attempts", DEFAULT_MAX_ATTEMPTS),
        verbose=_flag("VERBOSE", False),
    )


settings = _load()
