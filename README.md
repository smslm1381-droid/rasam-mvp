# رصام

دستیار پرسش‌وپاسخ روی دیتابیس. کاربر به فارسی سوال می‌پرسد، رصام کوئری مونگو
می‌سازد، **اعتبارسنجی می‌کند**، اجرا می‌کند و نتیجه را برمی‌گرداند.

نقشه‌ی راه و وضعیت کار در [`PLAN.md`](PLAN.md) است. قواعد کار در
[`CLAUDE.md`](CLAUDE.md).

## راه‌اندازی

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env   # سپس مقادیرش را پر کنید
```

بررسی اینکه تنظیمات درست خوانده می‌شود:

```powershell
python -c "import config; print(config.settings)"
```

اگر متغیر ضروری‌ای در `.env` نباشد، پیام فارسی می‌گوید کدام‌ها کم است.
کلید مدل و رمز دیتابیس در این خروجی پوشانده می‌شوند.

## دستورها

| دستور | کار | از قدم |
|---|---|---|
| `python -c "import config; print(config.settings)"` | دیدن تنظیمات | ۱ |
| `docker compose up -d` | مونگوی محلی توسعه | ۲ |
| `python scripts/seed_mongo.py` | پرکردن دیتابیس از CSVها | ۲ |
| `python ask.py "سوال شما"` | پرسیدن سوال | ۶ |
| `pytest` | تست‌ها | ۲ |

## وضعیت

فاز ۱ — رسیدن به اولین نمونه‌ی کارکننده. قدم ۱ (اسکلت و تنظیمات) انجام شده.
