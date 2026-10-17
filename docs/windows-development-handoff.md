# ادامهٔ توسعه روی ویندوز دیگر

وضعیت انتقال در ۱۴۰۵/۰۷/۲۵: قدم‌های ۲۹ تا ۳۴ کامیت شده‌اند. کد اولیهٔ قدم ۳۵
در کامیت `8f577c1` موجود است؛ این قدم هنوز پذیرش نهایی نشده و نباید تمام‌شده حساب شود.
ادامه را از `PLAN.md` و سپس `CLAUDE.md` بخوانید.

## گرفتن پروژه و راه‌اندازی

Python 3.13 نسخهٔ ۶۴بیتی، Git و Docker Desktop با WSL2 نصب باشند. برای توسعهٔ
gateway به Node.js 24 و uv حداقل 0.12.3 نیز نیاز است. محیط‌های مجازی و ابزارهای
محلی ماشین قبلی را کپی نکنید؛ مسیرهای آن‌ها وابسته به ماشین است.

```powershell
git clone https://github.com/smslm1381-droid/rasam-mvp.git
cd rasam-mvp
git switch main
git pull --ff-only
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

در `.env` کلید معتبر مدل، رمزهای دیتابیس و مسیر داده را تنظیم کنید. رمزهای اتصال
مدیر و تنظیمات Docker باید با هم سازگار باشند؛ راهنما در `.env.example` است.
برای دادهٔ نمونه، چهار فایل `solar_telemetry.*.csv` را جداگانه منتقل کنید؛ در گیت نیستند.
بستهٔ آمادهٔ ماشین قبلی `exports/windows-transfer-demo-data.zip` فقط این چهار CSV را
دارد. آن را در `data/raw` باز کنید و `RASAM_CSV_DIR=data/raw` بگذارید.
فایل همراه `windows-transfer-demo-data.zip.sha256` برای بررسی سلامت انتقال است؛
خروجی `Get-FileHash .\windows-transfer-demo-data.zip -Algorithm SHA256` باید با آن یکسان باشد.

```powershell
docker compose up -d
.\.venv\Scripts\python.exe scripts/seed_mongo.py
.\.venv\Scripts\python.exe scripts/seed_mysql.py
.\.venv\Scripts\python.exe onboard.py check demo
.\.venv\Scripts\python.exe onboard.py check demo-mysql
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

بررسی آمادگی هر دو مشتری باید سبز باشد. آزمون‌های وابسته به زیرساخت آماده‌نشده
ممکن است skip شوند؛ این به معنی تأیید اجرای واقعی آن بخش نیست. seed را فقط روی
دیتابیس محلی دمو اجرا کنید، نه دیتابیس مشتری.

## سرویس مدل و لایسنس

از پوشهٔ `gateway`، دستورهای `npm ci` و `uv sync --locked` را اجرا کنید و راهنمای
`gateway/README.md` را برای ساخت `.dev.vars`، مهاجرت D1 و اجرای شبیه‌ساز دنبال کنید.
پس از آماده‌شدن `/health` در ترمینال دوم از ریشهٔ پروژه:

```powershell
$env:RASAM_GATEWAY_TEST_URL = "http://127.0.0.1:8787"
$env:NO_PROXY = "127.0.0.1,localhost,::1"
.\.venv\Scripts\python.exe -m pytest tests/gateway -q
```

پوشهٔ `.wrangler` و لایسنس‌های آزمایشی محلی منتقل نمی‌شوند؛ D1 محلی را دوباره بسازید
و با ابزار مدیریت لایسنس، کلید آزمایشی تازه صادر کنید. استقرار واقعی Cloudflare هنوز
انجام نشده؛ `database_id` در `wrangler.toml` هنوز مقدار صفر دارد. روی ماشین جدید
صاحب حساب باید ورود مرورگر را انجام دهد؛ سپس مراحل استقرار همان راهنما اجرا شوند.
کلید مدل فقط در secrets سرویس سرور قرار می‌گیرد.

برای اجرای نسخهٔ رومیزی با سرویس محلی:

```powershell
$env:RASAM_GATEWAY_URL = "http://127.0.0.1:8787"
.\.venv\Scripts\python.exe rasam_desktop.py
```

نسخهٔ رومیزی `.env` را نمی‌خواند. کلید لایسنس و رمز اتصال را از رابط وارد کنید؛
انبار امن ویندوز ماشین قبلی با clone منتقل نمی‌شود. اگر تنظیمات یک نصب واقعی
لازم است، `%APPDATA%\Rasam` را جداگانه و امن منتقل کنید و رمزها را دوباره وارد کنید؛
این پوشه و فایل‌های راز نباید به گیت اضافه شوند.

آزمون تحویل این ماشین: اجرای کامل ۷۹۱ موفق، ۹۶ skip و سه خطای اتصال D1 داشت.
هر سه خطا از عبور اتصال loopback از پراکسی محیط بودند؛ با `NO_PROXY` بالا، اجرای
دوبارهٔ `tests/gateway/test_d1.py` هر سه را موفق کرد. دیتابیس‌های Docker و Python Worker
در زمان تحویل روشن نبودند؛ تأیید دوبارهٔ آن آزمون‌ها روی ماشین مقصد لازم است.

## نقطهٔ ادامه

### انتقال بدون دسترسی پوش

در زمان تحویل، پوش با خطای ۴۰۳ رد شد: حساب متصل `naderelqotb-rgb` اجازهٔ نوشتن
در مخزن `smslm1381-droid/rasam-mvp` ندارد. تمام تغییرات در شاخهٔ محلی `main` ثبت شده‌اند.
بستهٔ آفلاین `exports/rasam-mvp-handoff.bundle` تاریخچهٔ همین شاخه را دارد؛ آن و بستهٔ
CSV را روی سیستم مقصد ببرید. به‌جای clone اینترنتی می‌توانید اجرا کنید:

```powershell
git clone -b main .\rasam-mvp-handoff.bundle rasam-mvp
cd rasam-mvp
git remote set-url origin https://github.com/smslm1381-droid/rasam-mvp.git
```

پیش از `git pull` از مخزن آنلاین، ابتدا دسترسی نوشتن را درست کنید و شاخهٔ منتقل‌شده
را پوش کنید؛ مخزن آنلاین فعلاً از این نسخه عقب است. فایل bundle رازهای نادیده‌گرفته‌شده
را ندارد. دستورهای نصب محیط از بخش اول همان است؛ مرحلهٔ clone اینترنتی را تکرار نکنید.

۱. تکمیل تست مسیر `/license/status` روی D1 و خود Python Worker؛ تست‌های رابط قدم ۳۵
فعلاً عمدتاً با پاسخ شبیه‌سازی‌شده‌اند.
۲. آزمون واقعی فعال‌سازی، کلید غلط، هشدار هفت روز، انقضا و تمدید بدون نصب مجدد؛
پرسش واقعی از مسیر لایسنس و بررسی باقی‌ماندن دانش و تنظیمات.
۳. به‌روزرسانی PLAN و ثبت تکمیل قدم ۳۵ فقط پس از عبور از معیار پذیرش.
۴. پیش از قدم ۳۶ تصمیم کاربر دربارهٔ گواهی امضای نصب‌کننده لازم است؛ سپس قدم‌های
۳۶ تا ۳۸ طبق نقشه ادامه یابند. هنوز فایل نصبی ساخته نشده است.

ورود حساب Cloudflare، `.env`، `.dev.vars`، رمزها، داده‌های Docker و فایل‌های
Credential Manager عمداً در پوش گیت نیستند. برای انتقال رازها از روش امن جداگانه
استفاده کنید و آن‌ها را در چت، سند عمومی یا مخزن ننویسید.
