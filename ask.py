"""نقطه‌ی ورود خط فرمان: `python ask.py "سوال شما"`.

خود خط فرمان در `rasam/cli.py` است. این فایل فقط برای این است که دستور آشنا از
ریشه‌ی پروژه کار کند، و خطای تنظیمات را به‌جای traceback یک خط فارسی نشان بدهد.
"""

import sys

from rasam.errors import UserFacingError

try:
    from rasam.cli import main
except UserFacingError as error:  # پروفایل خراب یا `.env` ناقص — هنگام import تنظیمات
    print(f"خطا: {error}", file=sys.stderr)
    raise SystemExit(2)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
