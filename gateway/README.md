# سرور واسط رصام

این پوشه یک سرویس جدا برای Cloudflare Python Workers و D1 است و به نصب‌کنندهٔ مشتری
وارد نمی‌شود. کلید سرویس مدل فقط اینجا می‌ماند. برنامهٔ مشتری به `/v1/chat/completions`
درخواست می‌دهد و کلید لایسنس را در هدر Bearer می‌گذارد.

## اجرای محلی

Node.js نسخهٔ ۲۲ یا بالاتر، uv نسخهٔ ۰٫۱۲٫۳ یا بالاتر و Python لازم است.
ابزارها و پایگاه محلی به حساب Cloudflare نیاز ندارند.

```powershell
cd gateway
npm ci
uv sync
Copy-Item .dev.vars.example .dev.vars
# چهار مقدار .dev.vars را با اطلاعات سرویس خودتان پر کنید؛ فایل نادیده گرفته می‌شود.
uv run pywrangler d1 migrations apply DB --local
uv run pywrangler dev --ip 127.0.0.1 --port 8787
```

مسیر بررسی سلامت: `http://127.0.0.1:8787/health`. پایگاه محلی، خودِ شبیه‌ساز D1
در `.wrangler/` است؛ backend جایگزین SQLite در پایتون نداریم.

## مدیریت لایسنس

از ریشهٔ پروژه و محیط پایتون توسعه اجرا کنید؛ Node و uv باید در PATH باشند:

```powershell
python -m gateway.admin new acme --plan monthly
python -m gateway.admin new acme-year --plan yearly --daily-limit 40
python -m gateway.admin list
python -m gateway.admin extend HASH_FROM_LIST --days 30
python -m gateway.admin revoke HASH_FROM_LIST
```

کلید خام فقط هنگام صدور نمایش داده می‌شود؛ آن را به مشتری تحویل بدهید. پایگاه فقط هش
آن را نگه می‌دارد و دستورهای تمدید و ابطال، شناسهٔ هش در خروجی `list` را می‌گیرند.
تمدید از تاریخ دیرتر بین امروز و پایان اعتبار حساب می‌شود و لایسنس را فعال می‌کند.
ماهانه فعلاً ۳۰ روز و سالانه ۳۶۵ روز است. سهمیهٔ پیش‌فرض هر دو ۲۰ **درخواست مدل** در روز
است، با شروع روز UTC. هر سؤال ممکن است چند درخواست برای تولید، خلاصه، ترمیم یا نمودار
داشته باشد. افزایش شمارنده اتمی است؛ درخواست‌های هم‌زمان نمی‌توانند از سقف عبور کنند.
سهمیه هنگام ارسال به سرویس مدل مصرف می‌شود؛ تلاش ناموفق سرویس هم شمرده می‌شود.

برای اتصال توسعه، `RASAM_LLM_BASE_URL` را `http://127.0.0.1:8787/v1` و
`RASAM_LLM_API_KEY` را کلید لایسنس بگذارید؛ `RASAM_LLM_MODEL` باید مقدار غیرخالی داشته
باشد. مدل واقعی را سرور از `UPSTREAM_MODEL` انتخاب می‌کند؛ انتخاب مدل گران‌تر از سمت
مشتری ممکن نیست. مسیر فعلی فقط متن و پاسخ بدون جریان را پشتیبانی می‌کند.

## استقرار واقعی

۱. روی ویندوز ابتدا `npm install -g @napi-rs/keyring@1.3.0` و سپس
`uv run pywrangler login --use-keyring --scopes account:read user:read workers_scripts:write d1:write`
را اجرا کنید تا ورود حساب در انبار امن سیستم نگه داشته شود. ورود و تأیید دسترسی در
مرورگر را صاحب حساب انجام می‌دهد.
۲. `uv run pywrangler d1 create rasam-licenses` را اجرا کنید و شناسهٔ واقعی را در
`wrangler.toml` جایگزین شناسهٔ صفر کنید.
۳. `uv run pywrangler d1 migrations apply DB --remote` را اجرا کنید.
۴. مقدارهای `UPSTREAM_API_KEY`، `UPSTREAM_BASE_URL` و `UPSTREAM_MODEL` را با
`uv run pywrangler secret put NAME` ثبت کنید؛ کلید را در چت یا فایل عمومی ننویسید.
۵. `uv run pywrangler deploy` را اجرا کنید. مدیریت پایگاه واقعی از ریشهٔ پروژه:
`python -m gateway.admin --remote new acme --plan monthly`.

متن پرسش و نتیجه در D1 نوشته نمی‌شود؛ پایگاه فقط اطلاعات اشتراک و شمارنده دارد.
لاگ محتوای تماس نداریم و observability خودکار Worker خاموش است. نگهداری داده توسط
سرویس مدل تابع تنظیمات همان سرویس است. نسخهٔ فعلی درگاه پرداخت یا پنل مدیریت وب ندارد.

## آزمون

`python -m pytest tests/gateway -q` از ریشهٔ پروژه، قرارداد HTTP و سهمیه را روی
Miniflare واقعی بررسی می‌کند. برای آزمون خودِ Python Worker، ابتدا مهاجرت محلی و
`pywrangler dev` را اجرا کنید، سپس در ترمینال دوم:

```powershell
$env:RASAM_GATEWAY_TEST_URL="http://127.0.0.1:8787"
python -m pytest tests/gateway -q
```

این آزمون یک لایسنس آزمایشی منقضی در D1 محلی می‌سازد و پس از آزمون حذف می‌کند؛ هیچ
تماسی با مدل ندارد. ساخت Worker فقط پنج فایل مجاز را از راه `build_worker.py` کپی
می‌کند؛ محیط‌های پایتون، ابزارهای Node و فایل راز وارد بسته نمی‌شوند.

در آزمون ویندوز، بازسازی هنگام اجرای درخواست باعث خطای داخلی `10054` در workerd شد.
اگر شبیه‌ساز با این خطا بسته شد، دستور `pywrangler dev` را دوباره اجرا کنید و پیش از
آزمون، منتظر پاسخ `/health` بمانید. سازندهٔ بسته، فایل یکسان را دوباره نمی‌نویسد تا
ساخت آزمایشی باعث راه‌اندازی مجدد بی‌دلیل نشود.

مراجع: [FastAPI روی Python Workers](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/)،
[دسترسی Python به D1](https://developers.cloudflare.com/d1/examples/query-d1-from-python-workers/).
