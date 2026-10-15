"""نقطه‌ی ورود ابزار تحویل مشتری: `python onboard.py new` و `python onboard.py check <نام>`.

خود ابزار در `rasam/onboard.py` است؛ این فایل فقط دستور آشنا را از ریشه‌ی پروژه
نگه می‌دارد، و خطای تنظیمات را به‌جای traceback یک خط فارسی نشان می‌دهد.
"""

import sys

from rasam.errors import UserFacingError

try:
    from rasam.onboard import main
except UserFacingError as error:
    print(f"خطا: {error}", file=sys.stderr)
    raise SystemExit(2)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
