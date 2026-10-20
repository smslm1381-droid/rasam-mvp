"""آزمون مستقیم چند مدل؛ بدون گراف، دیتابیس یا تغییر تنظیم مدل اصلی."""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rasam import config


def check_model(client, settings, model, question):
    # فقط یک درخواست می‌فرستیم تا خطا با تلاش مجدد پنهان نشود.
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "max_tokens": settings.llm_max_tokens,
        "temperature": settings.llm_temperature,
    }
    started = time.monotonic()
    result = {"model": model, "ok": False}
    try:
        response = client.post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + settings.llm_api_key},
            json=payload,
        )
        result["http_status"] = response.status_code
        data = response.json()
        if response.status_code == 200:
            content = data["choices"][0]["message"]["content"]
            result["ok"] = isinstance(content, str) and bool(content.strip())
            result["answer"] = content if result["ok"] else "پاسخ متنی خالی است."
        else:
            result["error_code"] = data.get("error", {}).get("code")
            result["error_message"] = data.get("error", {}).get("message", "")
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
        result["failure_type"] = type(error).__name__
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    # پاسخ بیرونی هم ممکن است کلید را بازتاب دهد؛ پیش از چاپ پاک می‌شود.
    return json.dumps(result, ensure_ascii=False).replace(settings.llm_api_key, "[REDACTED]")


def main():
    parser = argparse.ArgumentParser(description="آزمون مستقیم مدل‌ها با تنظیمات فعلی API")
    parser.add_argument("models", nargs="+", help="شناسهٔ مدل‌های مورد آزمون")
    parser.add_argument("--question", default="به فارسی فقط بنویس: ارتباط برقرار است")
    args = parser.parse_args()
    settings = config.settings
    # HTTP/1.1 برای مقایسه با مسیر موفق سرور؛ هیچ تنظیمی ذخیره نمی‌شود.
    with httpx.Client(http2=False, timeout=settings.llm_timeout_ms / 1000,
                      follow_redirects=False) as client:
        for model in args.models:
            print(check_model(client, settings, model, args.question), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("اجرای تست ممکن نشد؛ نوع خطا:", type(error).__name__)
        sys.exit(1)
