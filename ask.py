"""نقطه‌ی ورود خط فرمان: `python ask.py "سوال شما"`.

خود خط فرمان در `rasam/cli.py` است. این فایل فقط برای این است که دستور آشنا از
ریشه‌ی پروژه کار کند.
"""

from rasam.cli import main

if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
