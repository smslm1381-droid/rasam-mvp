"""ورودی محیط سازمانی؛ نصب رومیزی و حساب شخصی دست‌کاری نمی‌شوند."""

import argparse
import getpass
import os
from pathlib import Path

from organization_portal.auth import Accounts
from organization_portal.errors import PortalError
from organization_portal.settings import from_environment
from organization_portal.store import LocalStore, RemoteStore


def initialize(args):
    if os.getenv("RASAM_ORG_LOCAL") == "1" and not os.getenv("RASAM_ORG_MASTER_KEY"):
        from organization_portal.local_key import read
        home = os.getenv("RASAM_ORG_HOME", "").strip()
        if not home:
            raise PortalError("ابتدا RASAM_ORG_HOME را تعیین کنید.")
        read(Path(home), create=True)
    settings = from_environment()
    store = LocalStore(settings.home / "organizations.sqlite3") if settings.local else RemoteStore(settings.storage_url, settings.storage_key)
    password = getpass.getpass("رمز مدیر کل، حداقل ۱۲ کاراکتر: ")
    if password != getpass.getpass("تکرار رمز: "):
        raise PortalError("تکرار رمز یکسان نیست.")
    Accounts(store).create(args.email, args.name, password, platform_admin=True)
    print("حساب مرکزی مدیر کل ساخته شد؛ رمز خام ذخیره یا چاپ نشد.")


def serve():
    import uvicorn
    from organization_portal.app import create_app
    from organization_portal.build_assets import build
    settings = from_environment()
    build()
    app = create_app(settings)
    port = int(os.getenv("PORT", os.getenv("RASAM_ORG_PORT", "8795")))
    host = "127.0.0.1" if settings.local else "0.0.0.0"
    uvicorn.run(app, host=host, port=port, access_log=False, log_level="warning")


def main(argv=None):
    parser = argparse.ArgumentParser(description="محیط سازمانی رصام")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="ساخت حساب مدیر کل با ورود تعاملی رمز")
    init.add_argument("--email", required=True)
    init.add_argument("--name", default="مدیر رصام")
    commands.add_parser("serve", help="اجرای وب‌اپ سازمانی")
    args = parser.parse_args(argv)
    try:
        initialize(args) if args.command == "init" else serve()
        return 0
    except PortalError as error:
        print(error.message)
        return 1
    except (OSError, ValueError):
        print("اجرای محیط سازمانی کامل نشد؛ تنظیمات و راهنمای نصب را بررسی کنید.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
