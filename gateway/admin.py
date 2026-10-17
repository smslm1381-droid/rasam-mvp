"""صدور، تمدید و ابطال دستی؛ کلید لایسنس فقط هنگام صدور نمایش داده می‌شود."""

import argparse
from datetime import datetime, timezone
import re
import secrets
import time

from gateway import d1_cli, licenses

HASH = re.compile(r"^[a-f0-9]{64}$")


def issue(customer, plan, daily_limit=20, now=None):
    if not customer.strip() or len(customer) > 200 or not 1 <= daily_limit <= 100000:
        raise ValueError("نام مشتری یا سهمیه معتبر نیست.")
    if plan not in ("monthly", "yearly"):
        raise ValueError("پلن باید monthly یا yearly باشد.")
    now = int(time.time()) if now is None else now
    key = "rasam_" + secrets.token_urlsafe(32)
    digest = licenses.token_hash(key)
    expires = now + (30 if plan == "monthly" else 365) * 86400
    values = [d1_cli.literal(value) for value in (digest, customer.strip(), plan)]
    sql = ("INSERT INTO licenses(token_hash, customer, plan, expires_at, daily_limit) VALUES ("
           + ", ".join(values) + f", {expires}, {daily_limit});")
    return key, digest, expires, sql


def change(identifier, days=None, now=None):
    if not HASH.fullmatch(identifier):
        raise ValueError("شناسهٔ لایسنس باید همان هش ۶۴حرفی فهرست باشد؛ کلید خام را اینجا ننویسید.")
    if days is None:
        return f"UPDATE licenses SET active = 0 WHERE token_hash = '{identifier}' RETURNING token_hash;"
    if not 1 <= days <= 3650:
        raise ValueError("تعداد روز تمدید باید بین ۱ و ۳۶۵۰ باشد.")
    now = int(time.time()) if now is None else now
    return (f"UPDATE licenses SET active = 1, expires_at = MAX(expires_at, {now}) + {days * 86400} "
            f"WHERE token_hash = '{identifier}' RETURNING token_hash;")


def parser():
    result = argparse.ArgumentParser(description="مدیریت لایسنس رصام در D1")
    result.add_argument("--remote", action="store_true", help="پایگاه واقعی Cloudflare؛ پیش‌فرض شبیه‌ساز محلی است")
    commands = result.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new")
    new.add_argument("customer")
    new.add_argument("--plan", choices=("monthly", "yearly"), required=True)
    new.add_argument("--daily-limit", type=int, default=20)
    for command in ("extend", "revoke"):
        action = commands.add_parser(command)
        action.add_argument("identifier")
        if command == "extend":
            action.add_argument("--days", required=True, type=int)
    commands.add_parser("list")
    return result


def run(args):
    if args.command == "new":
        key, identifier, expires, sql = issue(args.customer, args.plan, args.daily_limit)
        d1_cli.execute(sql, args.remote)
        print("شناسه:", identifier)
        print("پایان اعتبار (UTC):", datetime.fromtimestamp(expires, timezone.utc).isoformat())
        print("کلید لایسنس (فقط همین بار نمایش داده می‌شود):", key)
        return 0
    if args.command in ("extend", "revoke"):
        rows = d1_cli.execute(change(args.identifier, getattr(args, "days", None)), args.remote)
        print("لایسنس به‌روز شد." if rows else "لایسنسی با این شناسه پیدا نشد.")
        return 0 if rows else 1
    rows = d1_cli.execute("SELECT token_hash, customer, plan, expires_at, daily_limit, active, usage_day, used FROM licenses ORDER BY customer;", args.remote)
    for row in rows:
        print(row)
    return 0


def main(argv=None):
    try:
        return run(parser().parse_args(argv))
    except Exception:
        print("مدیریت لایسنس انجام نشد؛ ورودی‌ها، نصب ابزارهای uv و Node و تنظیمات D1 را بررسی کنید.")
        return 1


if __name__ == "__main__":
    from rasam.console import use_utf8
    use_utf8()
    raise SystemExit(main())
