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
python -c "from rasam import config; print(config.settings)"
```

اگر متغیر ضروری‌ای در `.env` نباشد، پیام فارسی می‌گوید کدام‌ها کم است.
کلید مدل و رمز دیتابیس در این خروجی پوشانده می‌شوند.

## دستورها

| دستور | کار | از قدم |
|---|---|---|
| `python -c "from rasam import config; print(config.settings)"` | دیدن تنظیمات | ۱ |
| `docker compose up -d` | مونگوی محلی توسعه | ۲ |
| `python scripts/seed_mongo.py` | پرکردن دیتابیس از CSVها | ۲ |
| `python ask.py "سوال شما"` | پرسیدن سوال | ۶ |
| `python onboard.py new` | ساختن پوشه‌ی مشتری تازه | ۲۶ |
| `python onboard.py check <نام>` | بررسی آمادگی تحویل مشتری | ۲۷ |
| `python ask.py --csv result.csv "سوال شما"` | ذخیره‌ی نتیجه به CSV | ۱۴ |
| `python ask.py --excel result.xlsx "سوال شما"` | ذخیره‌ی نتیجه به Excel | ۱۴ |
| `uvicorn rasam.api:app --reload` | اجرای API | ۱۳ |
| `pytest` | تست‌ها | ۲ |

## ساختار پروژه

کد به سه دسته تقسیم شده، بر اساس اینکه با آمدن مشتری تازه چه چیزی عوض می‌شود:

```
rasam-mvp/
├── ask.py · onboard.py         ← نقطه‌ی ورود خط فرمان و ابزار تحویل مشتری
├── rasam/                      ← همه‌ی کد برنامه
│   ├── config.py · errors.py   ← تنظیمات از .env؛ خطاهایی که پیامشان برای کاربر است
│   ├── customer.py             ← خواندن و اعتبارسنجی پروفایل مشتری
│   ├── cli.py · api.py         ← دو لایه‌ی نمایش؛ هیچ منطقی ندارند
│   ├── onboard.py              ← زیرفرمان‌های `new` و `check`
│   ├── core/                   ← ① برای همه‌ی مشتری‌ها و همه‌ی دیتابیس‌ها یکی
│   │   ├── graph.py            ← مسیر پاسخ: ساخت کوئری ← گارد ← اجرا ← خلاصه
│   │   ├── llm.py              ← تنها دروازه به مدل زبانی
│   │   ├── prompts.py          ← پرامپت خلاصه و نمودار، و محصورسازی
│   │   ├── knowledge.py        ← خواندن دانش مشتری و شاخص معنایی
│   │   ├── answer.py           ← `Answer`، تنها چیزی که لایه‌های نمایش می‌شناسند
│   │   ├── readiness.py        ← بررسی آمادگی تحویل
│   │   ├── charting.py · exporting.py
│   └── databases/              ← ② برای هر نوع دیتابیس یک پوشه
│       ├── base.py             ← قراردادی که هر دیتابیس پیاده می‌کند
│       ├── registry.py         ← db_type پروفایل ← کلاس همان دیتابیس
│       ├── mongodb/            ← schema · guard · prompts · reply · agent · attacks.yaml
│       └── postgresql/         ← اسکلت (ثبت‌نشده؛ دیتابیس دوم به‌تعویق، تصمیم ۷۹)
├── customers/                  ← ③ برای هر مشتری یک پوشه، بدون کد
│   └── demo/                   ← profile.yaml · documentation.md · examples.yaml ·
│                                  field_notes.yaml · golden_questions.yaml
├── templates/customer/         ← الگوی پوشه‌ی مشتری تازه (ابزار تحویل از آن می‌چیند)
├── scripts/                    ← seed_mongo.py · evaluate.py
├── docs/                       ← onboarding.md · adding-a-database.md
└── tests/                      ← هم‌شکل با rasam/ و customers/؛ conformance/ برای آزمون انطباق
```

- **مشتری تازه با دیتابیس آشنا:** `python onboard.py new` و تکمیل دانش با خود مشتری —
  مسیر کامل در [`docs/onboarding.md`](docs/onboarding.md). هیچ کدی عوض نمی‌شود.
- **مشتری تازه با دیتابیس تازه:** یک پوشه در `rasam/databases/` که قرارداد
  `base.py` را پیاده کند و آزمون انطباق را سبز کند، و یک خط در `registry.py` —
  [`docs/adding-a-database.md`](docs/adding-a-database.md).

## امنیت — و حدِ آن

هر کوئری‌ای که مدل می‌سازد، پیش از اجرا از گارد همان دیتابیس رد می‌شود (برای مونگو `rasam/databases/mongodb/guard.py`): فهرست سفید
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
uvicorn rasam.api:app --reload
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

فاز ۴ — پروفایل و بازیابی معنایی آماده‌اند؛ زیرساخت دیتابیس دوم در حال تکمیل است.
