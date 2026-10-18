"""آزمون اختیاری انبار امن مک با یک نام موقت؛ لایسنس و رمز اتصال کاربر خوانده نمی‌شوند."""

import secrets
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rasam import vault


def main():
    if sys.platform != "darwin":
        print("این بررسی باید روی مک و در نشست کاربر انجام شود.")
        return 1
    name = "MAC_TEST_" + uuid4().hex.upper()
    value = secrets.token_urlsafe(32)
    try:
        if not vault.write_secret(name, value).ok:
            print("ذخیره در Keychain موفق نبود؛ دسترسی انبار امن را روی مک بررسی کنید.")
            return 1
        read = vault.read_secret(name)
        if not read.ok or read.value != value:
            print("بازخوانی مقدار آزمایشی Keychain موفق نبود.")
            return 1
        print("نوشتن و بازخوانی انبار امن موفق بود؛ مقدار راز چاپ نمی‌شود.")
    finally:
        removed = vault.delete_secret(name)
    if not removed.ok:
        print("حذف مقدار آزمایشی موفق نبود؛ نتیجهٔ Keychain کامل نیست.")
        return 1
    print("مقدار آزمایشی پاک شد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
