"""نقطهٔ ورود رومیزی؛ محیط اجرا پیش از بارگذاری تنظیمات مشخص می‌شود."""

import os
import sys

from rasam import console

os.environ["RASAM_DESKTOP"] = "1"
console.use_utf8()

from rasam.desktop.launcher import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
