"""آزمون جداگانهٔ GapGPT؛ تنظیمات و کلید اصلی رصام دست‌نخورده می‌مانند."""

from pathlib import Path

import httpx
from dotenv import dotenv_values


def show_response(response, key, model):
    print("Model:", model)
    print("HTTP:", response.status_code)
    # خطای شبکه یا سرویس لزوماً قالب خطای استاندارد OpenAI ندارد.
    try:
        data = response.json()
    except ValueError:
        print("Response:", response.text.replace(key, "[REDACTED]")[:1500])
        return 1
    if response.status_code == 200 and isinstance(data, dict):
        text = data["choices"][0]["message"]["content"]
    else:
        error = data.get("error", data) if isinstance(data, dict) else data
        if isinstance(error, dict):
            text = error.get("message") or str(error)
        else:
            text = str(error)
    print(str(text or "پاسخ خالی است.").replace(key, "[REDACTED]"))
    return 0 if response.status_code == 200 and text else 1


def main():
    settings = dotenv_values(Path(__file__).resolve().parent / ".env.gapgpt")
    key = settings.get("RASAM_LLM_API_KEY")
    model = settings.get("RASAM_LLM_MODEL")
    base_url = settings.get("RASAM_LLM_BASE_URL")
    if not key or not model or not base_url:
        print("کلید، مدل یا نشانی سرویس در فایل .env.gapgpt تنظیم نشده است.")
        return 1
    if base_url.rstrip("/") not in {"https://api.gapgpt.app/v1", "https://api.gapapi.com/v1"}:
        print("نشانی سرویس باید یکی از دو نشانی رسمی GapGPT باشد.")
        return 1
    try:
        # همان رفتار پیش‌فرض تست‌های موفق قبلی؛ تنظیم شبکهٔ سیستم عوض نمی‌شود.
        with httpx.Client(http2=False, timeout=90) as client:
            response = client.post(
                base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + key},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "به فارسی فقط بنویس: ارتباط برقرار است"}],
                    "max_tokens": int(settings.get("RASAM_LLM_MAX_TOKENS") or 1024),
                    "temperature": 0.1,
                },
            )
        return show_response(response, key, model)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
        print("ارتباط یا پاسخ ناموفق بود؛ نوع خطا:", type(error).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
