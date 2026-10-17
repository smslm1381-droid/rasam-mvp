# ساخت نسخهٔ آزمایشی ویندوز

ساخت با Python 3.13 و PyInstaller پوشه‌ای انجام می‌شود. Inno Setup 6.7.3 کامپایلر
نصب‌کننده است. ابزار ساخت از وابستگی اجرای برنامه جداست:

```powershell
.\.venv\Scripts\python.exe -m pip install -r packaging/windows/requirements.txt
.\.venv\Scripts\python.exe packaging/windows/build.py --gateway-url https://YOUR_WORKER.workers.dev --iscc "PATH\TO\ISCC.exe"
```

فقط برای آزمایش توسعه با Worker محلی، `--gateway-url http://127.0.0.1:8787 --local-test`
بدهید. چنین بسته‌ای روی سیستم مشتری کار نمی‌کند مگر سرویس آزمایشی همان‌جا روشن باشد؛
آن را به‌جای نسخهٔ دارای سرور عمومی تحویل ندهید. نشانی API مدل را اینجا وارد نکنید.

خروجی‌ها در `exports/windows-build`: پوشهٔ `dist/Rasam`، `RasamSetup.exe` و SHA-256.
نصب per-user است، Administrator لازم ندارد، میان‌بر Start دارد و میان‌بر دسکتاپ
اختیاری است. نسخهٔ آزمایشی به انتخاب کاربر امضا ندارد؛ امضا پیش از فروش بررسی شود.
فایل را از منبع تأییدشده بگیرید و با `Get-FileHash` بررسی کنید؛ اگر منشأ یا هش روشن
نیست، نصب نکنید. هیچ آنتی‌ویروس یا تنظیم امنیتی برای این آزمایش خاموش نمی‌شود.

داده، پروفایل و شاخص دانش در `%APPDATA%\Rasam` و رمزها در Credential Manager هستند؛
پوشهٔ برنامه حاوی مشتری یا کلید مدل نیست. حذف و نصب دوباره این داده‌ها را نگه
می‌دارد. بستن تب برنامه را متوقف نمی‌کند؛ از «خروج از رصام» استفاده کنید. اجرای
دوبارهٔ میان‌بر همان نشست روشن را باز می‌کند.

گردش‌کار `Windows installer` روی GitHub دستی اجرا می‌شود و URL عمومی Worker را
ورودی می‌گیرد. انتشار یا push خودکار انجام نمی‌شود. اجرای واقعی آن روی GitHub و
آزمون نصب روی Windows 10/11 تازه باید جداگانه ثبت شوند.

منابع: [PyInstaller](https://pyinstaller.org/en/stable/usage.html)،
[Inno Setup](https://jrsoftware.org/isinfo.php)،
[نصب portable ابزار Inno](https://jrsoftware.org/ishelp/topic_technotes.htm).
