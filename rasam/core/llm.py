"""تنها دروازه‌ی خروج پروژه به سرویس مدل زبانی.

هیچ فایل دیگری مستقیم با مدل حرف نمی‌زند. دلیلش این است که عوض‌کردن سرویس،
رفتن به مدل محلی، یا افزودن شمارش هزینه، همه باید تغییر در یک فایل باشد نه
جست‌وجو در کل پروژه.

این فایل نمی‌داند «رصام» چیست: پرامپت آماده می‌گیرد و متن پس می‌دهد. ساختن
پرامپت و خواندن جواب کار قدم ۶ است.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from langchain_openai import ChatOpenAI

from rasam import config
from rasam.core.licensing_messages import MESSAGES as LICENSE_MESSAGES

# پیام‌ها بر اساس کد وضعیت HTTP. هر پیام باید بگوید کاربر چه کار کند، نه فقط
# اینکه چیزی خراب شد.
_HTTP_MESSAGES = {
    # ۴۰۰ چند علت شایع دارد و سرویس‌ها یکسان رفتار نمی‌کنند — گوگل برای کلید
    # نامعتبر هم ۴۰۰ می‌دهد نه ۴۰۱. پس هر دو علت گفته می‌شود.
    400: (
        "سرویس مدل درخواست را رد کرد. دو علت شایع: "
        "۱) RASAM_LLM_API_KEY نامعتبر یا ناقص است. "
        "۲) سرویس پارامتر reasoning_effort را نمی‌شناسد — "
        "RASAM_LLM_REASONING_EFFORT را روی unset بگذارید."
    ),
    401: "کلید سرویس مدل پذیرفته نشد. مقدار RASAM_LLM_API_KEY را بررسی کنید.",
    403: "این کلید اجازه‌ی دسترسی به این مدل را ندارد.",
    404: "مدل یا آدرس سرویس پیدا نشد. RASAM_LLM_MODEL و RASAM_LLM_BASE_URL را بررسی کنید.",
    402: "اعتبار حساب سرویس مدل کافی نیست.",
    429: "سرویس مدل درخواست‌ها را محدود کرده است. کمی بعد دوباره تلاش کنید.",
}


@dataclass(frozen=True)
class Result:
    """نتیجه‌ی یک تماس — یک *مقدار*، نه استثنا (قاعده‌ی امنیتی ۷).

    مثل `guard.Result`، در حالت شکست `text` برابر `None` است تا اگر فراخوان
    یادش رفت `ok` را چک کند فوراً بشکند، نه اینکه با یک رشته‌ی خالی جلو برود.
    """

    ok: bool
    text: str | None
    reason: str


def _fail(reason: str) -> Result:
    return Result(ok=False, text=None, reason=reason)


@lru_cache(maxsize=1)
def _client() -> ChatOpenAI:
    """کلاینت یک‌بار ساخته می‌شود و بین تماس‌ها می‌ماند.

    هر بار ساختن یعنی یک اتصال HTTP تازه؛ در قدم ۶ که برای هر سوال چند بار
    صدا زده می‌شود، این هزینه‌ی بی‌دلیل است.
    """
    settings = config.settings

    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        # بدون سقف توکن، بعضی سرویس‌ها کل پنجره‌ی خروجی مدل را هزینه‌ی احتمالی
        # می‌سنجند و خطای ۴۰۲ می‌دهند.
        max_tokens=settings.llm_max_tokens,
        # برای تولید کوئری، خروجی قطعی از خلاقیت مهم‌تر است.
        temperature=settings.llm_temperature,
        # پارامتر استانداردی که OpenAI، Gemini و OpenRouter هر سه می‌شناسند.
        # `None` یعنی اصلاً فرستاده نشود و پیش‌فرض سرویس بماند.
        reasoning_effort=settings.llm_reasoning_effort,
        # بدون این، پیش‌فرض کتابخانه ۱۰ دقیقه است — ۲۰۰ برابر زمان یک جواب
        # واقعی. کتابخانه ثانیه می‌خواهد، کانفیگ میلی‌ثانیه نگه می‌دارد تا با
        # بقیه‌ی سقف‌های پروژه هم‌واحد باشد.
        timeout=settings.llm_timeout_ms / 1000,
    )


def _gateway_failure(error):
    """فقط کدهای شناخته‌شده ترجمه می‌شوند؛ متن دلخواه سرور بازتاب داده نمی‌شود."""
    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return None
    detail = body.get("error", body)
    return LICENSE_MESSAGES.get(detail.get("code")) if isinstance(detail, dict) else None


def _describe_failure(error: Exception) -> str:
    """خطای سرویس را به پیام فارسی قابل‌فهم تبدیل می‌کند.

    به‌جای import از بسته‌ی `openai` (که وابستگی غیرمستقیم ماست) کد وضعیت از
    خودِ استثنا خوانده می‌شود. این برای هر سرویس سازگار با OpenAI کار می‌کند —
    از Gemini و OpenRouter تا مدل محلی.
    """
    gateway_message = _gateway_failure(error)
    if gateway_message:
        return gateway_message
    status = getattr(error, "status_code", None)
    if status in _HTTP_MESSAGES:
        return _HTTP_MESSAGES[status]
    if isinstance(status, int):
        if status >= 500:
            return "سرویس مدل الان در دسترس نیست. کمی بعد دوباره تلاش کنید."
        return f"سرویس مدل خطای {status} داد."

    # سرویس جواب داده ولی جوابش شکل انتظار را نداشت (مثلاً `choices` خالی).
    # این در اجرای واقعی با مدل‌های رایگان دیده شد و پیام «اینترنت را بررسی کنید»
    # گمراه‌کننده بود: اینترنت سالم است و مشکل از خود سرویس است.
    if isinstance(error, (ValueError, KeyError, TypeError, AttributeError)):
        return (
            f"سرویس مدل پاسخی داد که قابل‌خواندن نبود ({type(error).__name__}). "
            "دوباره بپرسید؛ اگر تکرار شد، مدل RASAM_LLM_MODEL را عوض کنید."
        )

    # نه کد وضعیتی آمده و نه پاسخی: یا شبکه قطع است یا آدرس سرویس غلط.
    return (
        f"تماس با سرویس مدل ناموفق بود ({type(error).__name__}). "
        "اتصال اینترنت و مقدار RASAM_LLM_BASE_URL را بررسی کنید."
    )


def _show(title: str, body: str) -> None:
    """چاپ عیب‌یابی. فقط پرامپت و پاسخ چاپ می‌شوند — هرگز کلید سرویس."""
    print(f"\n{'─' * 12} {title} {'─' * 12}\n{body}", flush=True)


def ask(prompt: str) -> Result:
    """پرامپت را به مدل می‌فرستد و متن جواب را برمی‌گرداند.

    هیچ استثنایی بیرون نمی‌دهد: هر شکستی — شبکه، کلید، سهمیه، پاسخ خالی — به
    یک `Result` با پیام فارسی تبدیل می‌شود.
    """
    if not prompt or not prompt.strip():
        return _fail("پرامپت خالی است.")

    if config.settings.verbose:
        _show("پرامپت", prompt)

    try:
        message = _client().invoke(prompt)
    except Exception as error:  # noqa: BLE001 — عمدی: هیچ خطایی نباید بیرون برود
        return _fail(_describe_failure(error))

    if config.settings.verbose:
        _show("پاسخ خام", repr(message.content))

    # مدل گاهی رشته‌ی خالی برمی‌گرداند. اگر همین‌جا گرفته نشود، چند لایه بالاتر
    # به شکل یک خطای عجیب و بی‌ربط ظاهر می‌شود.
    text = message.text.strip()
    if not text:
        return _fail("مدل پاسخ خالی برگرداند.")

    return Result(ok=True, text=text, reason="")


if __name__ == "__main__":
    import sys

    question = " ".join(sys.argv[1:]) or "به فارسی فقط بنویس: کار می‌کنم"
    answer = ask(question)
    print(answer.text if answer.ok else f"خطا: {answer.reason}")
    raise SystemExit(0 if answer.ok else 1)
