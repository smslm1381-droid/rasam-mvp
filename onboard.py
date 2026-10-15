"""نقطه‌ی ورود ابزار تحویل مشتری: `python onboard.py new`.

خود ابزار در `rasam/onboard.py` است؛ این فایل فقط دستور آشنا را از ریشه‌ی پروژه نگه می‌دارد.
"""

import sys

from rasam.onboard import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
