# رصام

دستیار پرسش‌وپاسخ روی دیتابیس. کاربر به فارسی سوال می‌پرسد، رصام کوئری (مونگو یا
SQL) می‌سازد، **اعتبارسنجی می‌کند**، اجرا می‌کند و نتیجه را برمی‌گرداند. دیتابیس‌ها:
**MongoDB** و **MySQL / MariaDB**.

نقشه‌ی راه و وضعیت کار در [`PLAN.md`](PLAN.md) است. قواعد کار در
[`CLAUDE.md`](CLAUDE.md).

## راه‌اندازی

**پیش‌نیازها:** Python 3.11 یا بالاتر، Git، و Docker Desktop (برای مونگو و MySQL محلی؛
روی ویندوز با WSL2). بدون Docker همه‌چیز جز آزمون‌هایی که به دیتابیس واقعی وصل می‌شوند
کار می‌کند — آن آزمون‌ها با پیام روشن skip می‌شوند، نه بی‌صدا سبز.

ویندوز (پاورشل):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env   # سپس مقادیرش را پر کنید
```

مک و لینوکس:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # سپس مقادیرش را پر کنید
```

بررسی اینکه تنظیمات درست خوانده می‌شود (روی هر دو یکی است):

```bash
python -c "from rasam import config; print(config.settings)"
```

اگر متغیر ضروری‌ای در `.env` نباشد، پیام فارسی می‌گوید کدام‌ها کم است.
کلید مدل و رمز دیتابیس در این خروجی پوشانده می‌شوند.

### نکته‌های ویندوز

- **اگر پاورشل فعال‌سازی را رد کرد** («running scripts is disabled»): یک بار
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` را بزنید.
- **ترمینال:** برای نمایش درست فارسی از **Windows Terminal** استفاده کنید؛ `cmd` قدیمی حروف
  را جدا و برعکس نشان می‌دهد. خروجی برنامه خودش UTF-8 است و روی کنسول ویندوز نمی‌افتد.
- **متغیر محیطی برای یک دستور:** در پاورشل به‌جای `RASAM_CUSTOMER=demo python ask.py …`
  (که فقط در bash کار می‌کند):

  ```powershell
  $env:RASAM_CUSTOMER = "demo-mysql"      # تا بستن همین پنجره می‌ماند
  python ask.py "سوال شما"
  Remove-Item Env:RASAM_CUSTOMER          # برگشت به مقدار `.env`
  ```

  راه ساده‌تر و همیشگی: `RASAM_CUSTOMER` را در `.env` عوض کنید.
- **ویرایش فایل‌ها:** Notepad قدیمی فایل UTF-8 را با BOM ذخیره می‌کند؛ برنامه آن را
  می‌خواند. ولی VS Code یا Notepad++ بهتر است. پایان خط را `.gitattributes` روی LF نگه می‌دارد،
  پس `git` ویندوز فایل‌ها را CRLF نمی‌کند (وگرنه آزمون‌های بایت‌به‌بایت می‌شکستند).
- **فایل CSV** خروجی با BOM ساخته می‌شود تا Excel ویندوز فارسی را درست نشان دهد.
- **اگر `pip install` روی `chromadb` یا `onnxruntime` شکست خورد:** معمولاً
  [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) کم است.

> **صادقانه:** همه‌ی کد و آزمون‌ها تاکنون روی مک اجرا شده‌اند. سازگاری با ویندوز با
> شبیه‌سازی شرایطش آزمون شده (`tests/test_windows.py`: کنسول غیر UTF-8، BOM، CRLF)، ولی
> دستورهای پاورشل بالا و نصب `chromadb` روی ویندوز واقعی هنوز اجرا نشده‌اند. اولین اجرای
> واقعی را با `pytest` شروع کنید و هر شکستی را اینجا ثبت کنید.

## دستورها

| دستور | کار | از قدم |
|---|---|---|
| `python -c "from rasam import config; print(config.settings)"` | دیدن تنظیمات | ۱ |
| `docker compose up -d` | مونگوی محلی توسعه | ۲ |
| `python scripts/seed_mongo.py` | پرکردن دیتابیس از CSVها | ۲ |
| `python scripts/seed_mysql.py` | پرکردن MySQL محلی با همان CSVها (برای مشتری `demo-mysql`) | ۲۱ |
| `python ask.py "سوال شما"` | پرسیدن سوال | ۶ |
| `python onboard.py new` | ساختن پوشه‌ی مشتری تازه | ۲۶ |
| `python onboard.py check <نام>` | بررسی آمادگی تحویل مشتری | ۲۷ |
| `python ask.py --csv result.csv "سوال شما"` | ذخیره‌ی نتیجه به CSV | ۱۴ |
| `python ask.py --excel result.xlsx "سوال شما"` | ذخیره‌ی نتیجه به Excel | ۱۴ |
| `uvicorn rasam.api:app --reload` | اجرای API | ۱۳ |
| `pytest` | تست‌ها (بدون Docker، آزمون‌های وابسته به دیتابیس skip می‌شوند) | ۲ |

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
│       └── mysql/              ← schema · guard · prompts · reply · agent · attacks.yaml
├── customers/                  ← ③ برای هر مشتری یک پوشه، بدون کد
│   ├── demo/                   ← نیروگاه نمونه روی MongoDB: profile.yaml · documentation.md ·
│   │                              examples.yaml · field_notes.yaml · golden_questions.yaml
│   └── demo-mysql/             ← همان داده روی MySQL؛ فقط همین پنج فایل
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

مک و لینوکس (bash):

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/ask \
	-H 'Content-Type: application/json' \
	-H 'X-API-Key: CHANGE_ME_API_KEY' \
	-d '{"question":"میانگین دمای داخلی اینورترها چقدر است؟"}'

# فایل: مقدار export را csv یا excel بفرستید
curl -X POST http://127.0.0.1:8000/ask \
	-H 'X-API-Key: CHANGE_ME_API_KEY' \
	-H 'Content-Type: application/json' \
	-d '{"question":"میانگین دما؟","export":"csv"}' \
	-o result.csv
```

ویندوز (پاورشل) — `curl` در پاورشل نام دیگری برای `Invoke-WebRequest` است و نقل‌قول
JSON را خراب می‌کند، پس از `Invoke-RestMethod` استفاده کنید. بدنه را **بایت UTF-8**
بفرستید، وگرنه فارسی خراب می‌رسد:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

$body = @{ question = "میانگین دمای داخلی اینورترها چقدر است؟" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ask `
    -Headers @{ "X-API-Key" = "CHANGE_ME_API_KEY" } `
    -ContentType "application/json; charset=utf-8" `
    -Body ([Text.Encoding]::UTF8.GetBytes($body))

# فایل
$body = @{ question = "میانگین دما؟"; export = "csv" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ask -OutFile result.csv `
    -Headers @{ "X-API-Key" = "CHANGE_ME_API_KEY" } `
    -ContentType "application/json; charset=utf-8" `
    -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

## وضعیت

فاز ۵ تمام است: دو دیتابیس (MongoDB و MySQL / MariaDB)، پروفایل سخت‌گیر مشتری، آزمون انطباق
مشترک، ابزار تحویل (`onboard.py new` و `check`). بعدی: فاز ۶ — نسخه‌ی رومیزی ویندوز.
جزئیات و تصمیم‌ها در [`PLAN.md`](PLAN.md).
