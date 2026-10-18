"""رمز اولیه فقط تصادفی و پرآنتروپی است؛ مقدار خام فقط در فایل خصوصی تحویل می‌شود."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from admin_panel.auth import ITERATIONS


def create(username, output):
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", username) or len(username) > 254:
        raise ValueError("نام کاربری باید ایمیل معتبر باشد.")
    env_file = ROOT / "admin_panel/.dev.vars"
    if output.exists() or env_file.exists():
        raise ValueError("تنظیم مدیر موجود است؛ پیش از تغییر، روش چرخش رمز را از راهنما بخوانید.")
    password = secrets.token_urlsafe(32)
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex()
    encoded = f"pbkdf2-sha256${ITERATIONS}${salt.hex()}${hashed}"
    values = {"ADMIN_USERNAME": username, "ADMIN_PASSWORD_HASH": encoded}
    origin = tomllib.loads((ROOT / "admin_panel/wrangler.toml").read_text())["vars"]["ADMIN_ORIGIN"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(f"Panel: {origin}\nUsername: {username}\nPassword: {password}\n")
    with env_file.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(key + "=" + json.dumps(value) for key, value in values.items()) + "\n")
    return output


def main():
    parser = argparse.ArgumentParser(description="آماده‌سازی امن مدیر رصام")
    parser.add_argument("--username", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "exports/private/admin-login.txt")
    args = parser.parse_args()
    try:
        result = create(args.username.strip(), args.output)
        print("تنظیم مدیر آماده شد؛ فایل خصوصی:", result.resolve())
        return 0
    except Exception as error:
        print(f"مدیر ساخته نشد ({type(error).__name__})؛ ایمیل، مسیر خروجی و وجود تنظیم قبلی را بررسی کنید.")
        return 1


if __name__ == "__main__":
    from rasam.console import use_utf8
    use_utf8()
    raise SystemExit(main())
