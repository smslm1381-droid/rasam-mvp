# محیط Codex پروژه

## محدوده و نسخه‌ها

تنظیم در ۲۰۲۶/۱۰/۱۷ روی Windows و Codex CLI `0.163.0-alpha.10.2` انجام شد.
کد برنامه و وابستگی‌های آن تغییر نکردند. این کار پذیرش برنامه یا تکمیل قدم ۳۵ نیست.

- دو مهارت پروژه از `affaan-m/ECC` (نام قبلی `everything-claude-code`) با commit
  `76aaa77df6adc5b889e689007bf99b9a4f74af34` نصب شدند.
- مسیر قابل کشف: `.agents/skills/{strategic-compact,verification-loop}/SKILL.md`؛
  متن اصلی در `UPSTREAM.md` نگهداری شده است. دستور اجرایی برای Codex/PowerShell
  تطبیق داده شد؛ hook و اسکریپت Claude نصب/فعال نشد.
- Codebase Memory `v0.12.1` از بستهٔ رسمی Windows amd64 در
  `.codex/tools/codebase-memory/codebase-memory-mcp.exe` قرار گرفت.
  SHA-256 بسته با `checksums.txt` انتشار یکسان بود:
  `4e4e0f16b45233af5c757a1fcbe3c3b16e9056375b1fbe2ce020b6de75dedcc0`.
  این بررسی checksum است، نه تأیید مستقل امضای انتشار.

## تنظیم و حافظه

سرور stdio با نام `codebase_memory_local` در `.codex/config.toml` همین پروژه
ثبت شده؛ فایل به‌دلیل مسیر مطلق ماشین از Git مستثناست. هیچ تنظیم سراسری تغییر نکرد.
اتصال افزونهٔ موجود با خطای 429 پاسخ داد و دست‌نخورده ماند؛ این سرور محلی جایگزین
قابل استفادهٔ این پروژه است، نه نصب دوبارهٔ اتصال راه‌دور.
فقط یکی از دو مسیر اتصال را در هر کار استفاده کن؛ در این پروژه محلی اولویت دارد.

شاخص و تنظیمات runtime در `.codex/cache/codebase-memory` هستند؛
`watcher_enabled=false`، `auto_watch=false` و `auto_index=false` تنظیم شدند.
ایندکس‌گذاری دستی است. نسخهٔ کنونی برای ارتباط داخلی daemon موقت الزامی دارد؛
این وابستگی دلیل اجرای daemon است، نه نیاز به watcher. daemon دائمی با
`daemon start` و سرویس شروع ویندوز نصب نشد. UI نیز فعال نشد.

حافظهٔ معتبر همان `PLAN.md` است: وضعیت، معماری، تصمیم‌ها و مسائل باز از قبل در آن
وجود دارند. پوشهٔ حافظهٔ موازی ساخته نشد. پیش از تحویل زمینه فقط تغییرات معنادار
و نتایج واقعی را ثبت کن. فشرده‌سازی خودکار خارجی نصب نشده؛ رفتار native Codex
حفظ شده و `/compact` فقط در سطحی که این فرمان را پشتیبانی می‌کند کاربرد دارد.
مهارت‌ها از نوبت بعد قابل استفاده‌اند؛ اتصال MCP تازه ممکن است نیازمند بازکردن
دوبارهٔ پروژه/جلسه باشد.

## بررسی دوباره در PowerShell

```powershell
$env:CBM_CACHE_DIR = Join-Path $PWD '.codex\cache\codebase-memory'
$env:CBM_ALLOWED_ROOT = $PWD.Path
$cbm = '.\.codex\tools\codebase-memory\codebase-memory-mcp.exe'
codex mcp get codebase_memory_local
& $cbm --version
& $cbm cli index_status --project rasam-mvp
& $cbm cli search_graph --project rasam-mvp --name-pattern '.*Answer.*' --limit 5
git diff --check
```

فقط اگر شاخص قدیمی یا ناقص شد:

```powershell
& $cbm cli index_repository --repo-path $PWD.Path --name rasam-mvp --mode moderate
```

برای انتقال ماشین، بستهٔ رسمی متناسب با معماری را دوباره با checksum بررسی کن
و مسیرهای `.codex/config.toml` را مطابق ریشهٔ تازه بنویس؛ باینری در Git نیست.
نسخهٔ پشتیبان فایل‌های موجود پیش از تغییر در
`%TEMP%\rasam-codex-setup\backup` ذخیره شد؛ فایل تنظیم سراسری آن ممکن است
حساس باشد و نباید وارد Git شود.

## روش سنجش هزینه

برای مقایسه، در دو جلسهٔ تازه با مدل و وضعیت یکسان مخزن، یک پرسش مشخص دربارهٔ
مسیر `Answer` را یک بار با گراف و یک بار با جست‌وجوی عادی اجرا کن. شمار تماس ابزار،
حجم خروجی و نتیجهٔ صحت را ثبت کن؛ توکن فقط از آمار واقعی خود Codex گزارش شود.
در این تنظیم آزمایش کنترل‌شدهٔ قبل/بعد انجام نشده و درصد صرفه‌جویی ادعا نمی‌شود.

## نتیجهٔ بررسی واقعی

- `codex mcp get codebase_memory_local`: فعال، stdio، مسیر صحیح پروژه.
- handshake واقعی `initialize` و `tools/list`: موفق، ۱۷ ابزار، exit 0.
- شاخص `moderate`: وضعیت `ready`، ۱۷۱۷ گره و ۶۸۳۸ رابطه؛ watcher خاموش.
- جست‌وجو: کلاس `rasam.core.answer.Answer` در `rasam/core/answer.py:14` پیدا شد.
  ردیابی `rasam.core.graph.answer` سه فراخوان از API، CLI و desktop نشان داد؛
  تحلیل وابستگی نیز `IMPORTS` و `DEPENDS_ON` را برگرداند.
- پوشش کامل نیست: `templates/customer/profile.yaml` در خطوط ۷–۱۶ تحلیل جزئی دارد؛
  `.env` عمداً خارج شاخص است. تحلیل رابطه جای خواندن منبع را نمی‌گیرد.
- TOML، manifest هر دو مهارت و نحو هر ۵۷ فایل Python بسته با AST بررسی شد؛ موفق.
  `git diff --check` موفق بود.
- اجرای هدفمند `pytest tests/test_architecture.py -q --tb=short` به‌علت
  `No module named pytest` انجام نشد؛ `.venv` محلی موجود نیست. تست‌های برنامه،
  دیتابیس واقعی، lint و type check تأیید نشده‌اند.
- ابزارهای موجود حذف یا تنظیم مجدد نشدند؛ آزمون تک‌تک اتصال‌های نامرتبط انجام نشد.
  هنگام بررسی، بخش `desktop` تنظیم سراسری توسط فرایندی خارج این تنظیم تغییر کرد؛
  بخش‌های دیگر با پشتیبان برابر بودند. این تغییر بازنویسی یا برگردانده نشد.
- Codex CLI ثبت سرور را می‌شناسد؛ استفاده از ابزار محلی در همین گفت‌وگوی از قبل
  بازشده بررسی نشده و ممکن است به جلسهٔ تازه نیاز داشته باشد.

## منابع

- [مهارت‌های Codex](https://developers.openai.com/codex/skills)
- [تنظیم MCP](https://developers.openai.com/codex/mcp)
- [فرمان‌های Codex](https://developers.openai.com/codex/cli/slash-commands)
- [ECC](https://github.com/affaan-m/ECC/tree/76aaa77df6adc5b889e689007bf99b9a4f74af34/skills)
- [انتشار Codebase Memory](https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.12.1)
