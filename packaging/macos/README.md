# ادامهٔ توسعه و ساخت رصام روی مک

وضعیت ۲۰۲۶/۱۰/۱۸: بستهٔ واقعی arm64 روی macOS 27.0.1 ساخته و تست شده است؛
گزارش و موارد باز در `docs/macos-review.md` و قدم ۴۳ `PLAN.md` ثبت‌اند. تست کامل
۹۹۲ موفق و ۵ skip مربوط به Worker داشت. فعال‌سازی، پاسخ و رویداد بازکردن مجدد
اپ تأیید شدند؛ پذیرش نصب تازه و ارتقای نسخه هنوز بازند؛
Intel هنوز ساخته و امتحان نشده است. دستورهای زیر برای تکرار روی هر معماری‌اند.
برای حفظ محیط قدیمی می‌توانید به‌جای `.venv` از `.venv-macos` استفاده کنید.

## ۱. دریافت کد و محیط تازه

روی مک، مخزن را clone کنید یا تغییرات را با `git pull --ff-only` دریافت کنید.
پوشهٔ `.venv` ویندوز را منتقل نکنید. Python 3.13 و ابزارهای Command Line Tools اپل
باید روی ماشین توسعه موجود باشند. از ریشهٔ مخزن:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: -r requirements.txt -r packaging/macos/requirements.txt
python -c 'import platform; print(platform.machine())'
```

Apple Silicon باید `arm64` و Intel باید `x86_64` نشان دهد. روی Apple Silicon اگر
`x86_64` دیدید، Python زیر Rosetta است و خروجی Intel می‌سازد؛ برای بستهٔ بومی از
Python arm64 استفاده کنید. دو بسته جدا ساخته می‌شوند؛ universal2 ادعا نمی‌شود.
وجود wheel برای وابستگی‌های هر معماری در همان نصب بررسی می‌شود؛ شکست نصب را ثبت
کنید و آن را با تغییر خودسرانهٔ نسخه‌ها یا حذف وابستگی پنهان نکنید.

## ۲. آزمون‌های بدون مدل و دیتابیس زنده

فایل `.env`، رمز ورود پنل و فایل‌های `exports/private` در Git نیستند. برای آزمون
واقعی بعدی، لایسنس آزمایشی را از پنل با همان دسترسی مدیریتی موجود صادر کنید و اطلاعات
فقط‌خواندنی دیتابیس را جداگانه و امن روی مک وارد کنید؛ راز را در Git یا چت ننویسید.
`localhost` روی مک، دیتابیس Docker ویندوز نیست. دیتابیس باید روی خود مک یا نشانی
شبکه‌ای مجاز و قابل‌دسترسی باشد؛ برای این انتقال هیچ درگاه یا فایروالی خودکار باز نمی‌شود.

این مقدارها فقط ورودی آزمایش‌اند و رمز واقعی نیستند؛ در بسته قرار نمی‌گیرند:

```bash
export RASAM_CUSTOMER=demo
export RASAM_MONGO_URI=mongodb://127.0.0.1:27017/solar_telemetry
export RASAM_LLM_API_KEY=build-test-placeholder
export RASAM_LLM_BASE_URL=https://example.invalid/v1
export RASAM_LLM_MODEL=build-test-model
python -m pytest tests/desktop tests/packaging tests/test_vault.py -q --tb=short
python packaging/macos/check_keychain.py
```

تست اول بدون مدل/دیتابیس زنده است. دستور دوم در نشست کاربر مک، یک نام تصادفی موقت
در Keychain می‌نویسد، می‌خواند و پاک می‌کند؛ نام لایسنس و اتصال کاربر را لمس نمی‌کند.
اگر سیستم درخواست دسترسی داد، خودتان آن را بررسی کنید. موفقیت تست‌های mock انبار
رمز، جای موفقیت دستور دوم را نمی‌گیرد. نتیجهٔ واقعی را در `PLAN.md` ثبت کنید.

## ۳. ساخت بومی روی همان مک

```bash
python packaging/macos/build.py --gateway-url https://rasam-gateway.nova-dd625a.workers.dev
```

خروجی پیش‌فرض `exports/macos-0.1.4-arm64/` یا `exports/macos-0.1.4-x86_64/` است:
`dist/Rasam.app`، فایل `Rasam-0.1.4-macOS-ARCH.dmg`، SHA-256 و `build-report.json`.
نسخه از `rasam/__init__.py` گرفته می‌شود؛ نام بالا مربوط به نسخهٔ فعلی است.
ابزار عمداً پوشهٔ خروجی موجود را بازنویسی نمی‌کند. برای تکرار، مسیر تازه بدهید:

```bash
python packaging/macos/build.py --gateway-url https://rasam-gateway.nova-dd625a.workers.dev --output exports/macos-retry-01
```

فقط برای Worker محلی صریحاً `--local-test --gateway-url http://127.0.0.1:8787` بدهید؛
بستهٔ محلی را به مشتری تحویل ندهید. برای تست فایل ساخته‌شده، مسیر معماری خود را بدهید:

```bash
RASAM_TEST_DESKTOP_EXECUTABLE="$PWD/exports/macos-0.1.4-arm64/dist/Rasam.app/Contents/MacOS/Rasam" python -m pytest tests/desktop/test_lifecycle.py -q
```

این آزمون پوشهٔ دادهٔ موقت دارد، بازشدن نمونهٔ دوم و خروج احرازشده را می‌سنجد؛
مرورگر، Keychain واقعی، Gatekeeper و پاسخ مدل را جایگزین نمی‌کند.

## ۴. نصب و پذیرش واقعی — قدم ۴۳

فایل DMG را باز و `Rasam.app` را به Applications بکشید؛ از روی DMG اجرا نکنید.
کاربر نهایی برای اجرای بسته نباید به Python محیط توسعه نیاز داشته باشد. این مسیر
را روی هر دو معماری، ترجیحاً در حساب تازه یا مک بدون Python، انجام و نتیجه را ثبت کنید:

1. بازکردن از Finder و نمایش رابط فارسی در مرورگر پیش‌فرض؛ آیکون Finder و Dock.
2. فعال‌سازی با لایسنس آزمایشی، بستن و بازکردن و حفظ لایسنس در Keychain.
3. اتصال فقط‌خواندنی MongoDB و MySQL/MariaDB، انتخاب منابع و ذخیرهٔ آموزش.
4. پرسش دارای پاسخ معلوم، جدول و نمودار و دریافت CSV/Excel؛ بدون چاپ کلید در گزارش.
5. اجرای دوم، بازکردن دوباره پس از بستن تب، «خروج از رصام» و آزادشدن درگاه/قفل.
6. جایگزینی نسخهٔ برنامه و حفظ داده در `~/Library/Application Support/Rasam` و Keychain.
7. ثبت پیام واقعی Gatekeeper و کمترین نسخهٔ macOS که واقعاً امتحان شده است.

کمترین macOS پشتیبانی‌شده هنوز تعیین نشده؛ استفادهٔ CI از macOS 15 تضمین نسخه‌های
قدیمی‌تر نیست. آزمون یک معماری، معماری دیگر را قبول‌شده نمی‌کند. در پایان فقط
لایسنس/دادهٔ مشخصاً موقت خود را پاک کنید؛ داده و راز شخصی کاربر تغییر نکند.

## امضا و انتشار

PyInstaller به‌صورت پیش‌فرض امضای فنی ad-hoc می‌سازد؛ ابزار `codesign --verify --deep
--strict` و سپس صحت DMG را بررسی می‌کند. ad-hoc، Developer ID یا notarization نیست.
روش امضای نهایی و انتشار پس از آزمون باید با صاحب محصول تعیین شود؛ هیچ گواهی،
عضویت پولی یا استثنای امنیتی ایجاد نشده است. اگر Gatekeeper اجرا را نپذیرفت، همان
نتیجه را ثبت کنید؛ خاموش‌کردن Gatekeeper یا حذف دسته‌جمعی quarantine راه پذیرش نیست.

گردش‌کار دستی `macOS trial package` در GitHub برای `macos-15` (arm64) و
`macos-15-intel` آماده است؛ با push خودکار اجرا نمی‌شود. اجرا روی GitHub و مصرف
دقایق احتمالی آن در این نوبت درخواست نشده و هنوز انجام نشده است. انتشار فایل‌های
مک روی سایت و تغییر دانلود، بعد از ساخت و پذیرش واقعی است؛ سایت فعلاً عرضهٔ مک
را آماده اعلام نمی‌کند. سرویس لایسنس همان سرویس مشترک می‌ماند.

منابع: [بستهٔ macOS در PyInstaller](https://pyinstaller.org/en/stable/spec-files.html#spec-file-options-for-a-macos-bundle)،
[معماری و امضای مک](https://pyinstaller.org/en/stable/feature-notes.html#macos-multi-arch-support)،
[runnerهای رسمی GitHub](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
