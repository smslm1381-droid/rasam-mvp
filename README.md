# رصام

دستیار پرسش‌وپاسخ روی دیتابیس. کاربر به فارسی سوال می‌پرسد، رصام کوئری (مونگو یا
SQL) می‌سازد، **اعتبارسنجی می‌کند**، اجرا می‌کند و نتیجه را برمی‌گرداند. دیتابیس‌ها:
**MongoDB** و **MySQL / MariaDB**.

نقشه‌ی راه و وضعیت کار در [`PLAN.md`](PLAN.md) است. قواعد کار در
[`CLAUDE.md`](CLAUDE.md).

برای ادامهٔ کار روی یک ویندوز تازه، [راهنمای انتقال توسعه](docs/windows-development-handoff.md)
شامل راه‌اندازی، فایل‌های خارج از گیت و نقطهٔ دقیق ادامه را بخوانید.

## راه‌اندازی

**پیش‌نیازها:** Python 3.13 (نسخهٔ آزموده‌شدهٔ توسعه؛ `.python-version`)، Git، و Docker Desktop (برای مونگو و MySQL محلی؛
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
  می‌توانید بدون تغییر تنظیمات ویندوز، پایتون محیط پروژه را مستقیم اجرا کنید:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest
  .\.venv\Scripts\python.exe ask.py "میانگین دمای داخلی اینورترها چقدر است؟"
  .\.venv\Scripts\python.exe -m uvicorn rasam.api:app --host 127.0.0.1 --port 8000
  ```

- **اگر Docker اجرا نمی‌شود:** ورود به حساب Docker جای نصب WSL را نمی‌گیرد.
  در PowerShell با دسترسی Administrator، دستور
  `wsl --install --no-distribution` را اجرا کنید؛ اگر درخواست شد ویندوز را ری‌استارت
  کنید و سپس Docker Desktop را باز کنید. `docker info` باید اطلاعات سرور را نشان دهد.
- **مسیر CSVهای دمو:** مقدار `RASAM_CSV_DIR` در `.env` باید به پوشه‌ای برسد که
  خودِ چهار فایل CSV در آن هستند. مسیر نسبی از ریشه‌ی پروژه حساب می‌شود؛ برای
  بستهٔ انتقال را در `data/raw` باز کنید و همین مسیر را تنظیم کنید. مسیر ماشین خودتان
  را در `.env` نگه دارید، نه در کد.
- **اجرای هم‌زمان پروژهٔ قدیمی:** کانتینرها با نام خودکار Compose و volumeهای همین
  پروژه ساخته می‌شوند. اگر پورت مونگو اشغال است، `RASAM_MONGO_PORT=27018` و پورت
  `RASAM_MONGO_URI` و `RASAM_MONGO_ADMIN_URI` را هم `27018` بگذارید. برای MySQL نیز
  `RASAM_MYSQL_PORT` و هر دو URI باید یک پورت داشته باشند. پورت‌ها فقط روی loopback
  منتشر می‌شوند؛ دیتابیس دمو از شبکهٔ بیرونی در دسترس نیست.
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

> **اجرای واقعی ویندوز (۱۴۰۵/۰۷/۲۴):** وابستگی‌ها، از جمله `chromadb`، در محیط
> `.venv` با Python 3.13 نصب شدند و API روی `127.0.0.1:8000/health` پاسخ `ok` داد.
> خواندن اولین متغیر `.env` با BOM و نام بسیار بلند یکی از تست‌ها اصلاح شد.
> اجرای کامل پس از آماده‌شدن دیتابیس‌ها: **۷۲۲ موفق، بدون شکست و بدون skip**.
> پس از ری‌استارت، WSL 3.0.3 نصب شد و موتور Docker 29.7.2 بالا آمد؛ socketهای موقت
> مانده از اجرای ناموفق، بدون حذف داده یا reset کارخانه کنار گذاشته شدند.
> وابستگی `pymysql[rsa]` نیز برای احراز هویت SHA-2 در MySQL به نصب اضافه شد.
> MongoDB 7.0.45 و MySQL 8.4.11 با داده‌های دمو اجرا شدند و بررسی آمادگی هر دو مشتری
> کاملاً سبز بود. پرسش واقعی CLI، خروجی CSV و Excel و نمودار API نیز موفق بودند.
> سنجهٔ عددی مدل واقعی: **۱۵/۱۵ سوال طلایی برای هر دیتابیس**؛ در این سنجه خلاصه و
> نمودار خاموش بودند و جداگانه از مسیر واقعی CLI/API امتحان شدند.

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

فاز ۵ تمام است؛ فاز ۶ در پذیرش نهایی است. نسخهٔ آزمایشی ویندوز `0.1.1` ساخته شده؛
نصب، حذف، اجرای دوم، خروج و ارتقای واقعی با حفظ تنظیمات و رمزها روی میزبان توسعه
آزموده شده‌اند. آخرین اجرای کامل پروژه ۹۲۶ تست موفق و بدون skip داشت؛ جزئیات در
[گزارش نصب‌کننده](docs/windows-installer-review.md).

کاربر نسخهٔ رومیزی Python نصب نمی‌کند. فایل `RasamSetup.exe` و SHA-256 آن در
`exports/windows-build/` ساخته می‌شوند. [راهنمای کاربر](docs/desktop-quickstart.md)،
[راهنمای پشتیبانی](docs/support-playbook.md) و [دستور ساخت](packaging/windows/README.md)
مسیر تحویل را توضیح می‌دهند. نسخهٔ آزمایشی به تصمیم صاحب پروژه امضا ندارد؛
انتشار پیوند عمومی دانلود، آزمون Windows 10/11 تازه و تمرین کاربر غیرفنی هنوز بازند.

[سایت معرفی رصام](https://rasam-product.nova-dd625a.workers.dev) شامل راهنمای نصب و
پرسش‌های متداول آنلاین است. دانلود فایل نصبی فعلاً منتظر فعال‌سازی R2 حساب است؛
دکمه تا بارگذاری واقعی غیرفعال می‌ماند. [راهنمای انتشار سایت](website/README.md).

سرویس لایسنس مستقل روی Cloudflare مستقر است:
`https://rasam-gateway.nova-dd625a.workers.dev`. کلید مدل فقط در secrets سرور می‌ماند؛
رمز دیتابیس در Credential Manager و پروفایل/دانش در `%APPDATA%\Rasam` است.
حذف یا ارتقا، این داده‌ها را حفظ می‌کند. اعلان نسخه فقط با پیوند دانلود منتشرشده
فعال می‌شود؛ نصب خودکار نداریم. [راهنمای Worker](gateway/README.md).

سنجهٔ ۱۵ سؤال از مسیر HTTP نیز قابل اجراست؛ خطای سرویس نتیجهٔ موفق نمی‌سازد:

```powershell
python scripts/evaluate.py --api-url http://127.0.0.1:8000 --pause 20
python scripts/evaluate.py --desktop-home "$env:APPDATA\Rasam" --pause 20
```

API کلید `RASAM_API_KEY` محیط توسعه را می‌گیرد؛ برای مسیر رومیزی برنامه باید باز و
لایسنس آماده باشد. مشتری محیط توسعه باید همان مشتری مقصد باشد. وضعیت پذیرش و نتیجهٔ
واقعی هر سنجه در [`PLAN.md`](PLAN.md) ثبت می‌شود؛ آزمون خودکار جای تمرین انسانی نیست.
