# رصام

دستیار پرسش‌وپاسخ روی دیتابیس. کاربر به فارسی سوال می‌پرسد، رصام کوئری مونگو
می‌سازد، **اعتبارسنجی می‌کند**، اجرا می‌کند و نتیجه را برمی‌گرداند.

نقشه‌ی راه و وضعیت کار در [`PLAN.md`](PLAN.md) است. قواعد کار در
[`CLAUDE.md`](CLAUDE.md).

## راه‌اندازی

مک و لینوکس:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # سپس مقادیرش را پر کنید
```

ویندوز (پاورشل):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env   # سپس مقادیرش را پر کنید
```

بررسی اینکه تنظیمات درست خوانده می‌شود:

```bash
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
| `python ask.py --csv result.csv "سوال شما"` | ذخیره‌ی نتیجه به CSV | ۱۴ |
| `python ask.py --excel result.xlsx "سوال شما"` | ذخیره‌ی نتیجه به Excel | ۱۴ |
| `uvicorn api.main:app --reload` | اجرای API | ۱۳ |
| `pytest` | تست‌ها | ۲ |

## امنیت — و حدِ آن

هر کوئری‌ای که مدل می‌سازد، پیش از اجرا از `guard.py` رد می‌شود: فهرست سفید
مرحله‌ها و عملگرها، ردِ قطعی هر چیزی که کد اجرا می‌کند یا در دیتابیس می‌نویسد،
فهرست کالکشن‌های مجاز، و سقف زمان. اتصال دیتابیس هم فقط-خواندنی است.

سوال کاربر پیش از ورود به پرامپت محصور و کوتاه می‌شود تا فریب‌دادن مدل سخت‌تر
شود. **ولی این تضمین صددرصد نیست و چنین ادعایی نمی‌کنیم.** هدف محدودکردن
*پیامد* یک تزریق موفق است: بدترین حالت باید یک پاسخ اشتباه باشد — نه تغییر
داده، نه اجرای کد روی سرور دیتابیس، نه افشای کالکشن‌های دیگر. آن تضمین دوم کار
گارد است، نه محصورسازی.

## API

پیش از اجرای API، مقدار `RASAM_API_KEY` را در `.env` با یک کلید قوی عوض کنید.

```bash
uvicorn api.main:app --reload
```

سلامت سرویس بدون کلید در دسترس است:

```bash
curl http://127.0.0.1:8000/health
```

برای پرسیدن سوال، کلید را در header بفرستید:

```bash
curl -X POST http://127.0.0.1:8000/ask \
	-H 'Content-Type: application/json' \
	-H 'X-API-Key: CHANGE_ME_API_KEY' \
	-d '{"question":"میانگین دمای داخلی اینورترها چقدر است؟"}'
```

برای دریافت فایل از API، مقدار `export` را `csv` یا `excel` بفرستید:

```bash
curl -X POST http://127.0.0.1:8000/ask \
	-H 'X-API-Key: CHANGE_ME_API_KEY' \
	-H 'Content-Type: application/json' \
	-d '{"question":"میانگین دما؟","export":"csv"}' \
	-o result.csv
```

## وضعیت

فاز ۴ — پروفایل مشتری و بازیابی معنایی آماده‌اند؛ قدم بعدی افزودن دیتابیس دوم است.
