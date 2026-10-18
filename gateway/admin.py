"""صدور، تمدید و ابطال دستی؛ کلید لایسنس فقط هنگام صدور نمایش داده می‌شود."""

import argparse
from datetime import datetime, timezone

from gateway import d1_cli
from gateway.license_commands import issue, change, quota

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
    limit = commands.add_parser("quota")
    limit.add_argument("identifier")
    limit.add_argument("--daily-limit", required=True, type=int)
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
    if args.command == "quota":
        rows = d1_cli.execute(quota(args.identifier, args.daily_limit), args.remote)
        print("سهمیه به‌روز شد." if rows else "لایسنسی با این شناسه پیدا نشد.")
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
