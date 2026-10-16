"""نقطه‌ی ورود خط فرمان: `python ask.py "سوال شما"`.

خود خط فرمان در `rasam/cli.py` است. این فایل فقط برای این است که دستور آشنا از
ریشه‌ی پروژه کار کند، و خطای تنظیمات را به‌جای traceback یک خط فارسی نشان بدهد.
"""

import sys

from rasam import console
from rasam.errors import UserFacingError

# پیش از هر چاپی: کنسول ویندوز فارسی را با UTF-8 نمی‌پذیرد (rasam/console.py).
console.use_utf8()

try:
    from rasam import config
    if config.settings is None:
        config.settings = config._load()
    from rasam.cli import main
except UserFacingError as error:  # پروفایل خراب یا `.env` ناقص — هنگام import تنظیمات
    print(f"خطا: {error}", file=sys.stderr)
    raise SystemExit(2)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
