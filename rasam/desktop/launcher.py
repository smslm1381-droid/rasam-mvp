"""سوکت پیش از انتخاب درگاه به سرور سپرده می‌شود تا فاصلهٔ آزادبودن و استفاده نداشته باشیم."""

from __future__ import annotations

import argparse
import socket
import sys

import uvicorn

from rasam import config
from rasam.desktop.app import create_app
from rasam.desktop.instance import DesktopInstance
from rasam.desktop.browser import open_page
from rasam.desktop.startup_error import record_error
from rasam.errors import UserFacingError


def serve(open_browser: bool = True) -> int:
    instance = DesktopInstance(config.DATA_HOME)
    try:
        if not instance.acquire():
            url = instance.wait_url()
            if not url:
                raise OSError("starting instance unavailable")
            if open_browser:
                open_page(url)
            return 0
        return run_server(instance, open_browser)
    finally:
        instance.close()


def run_server(instance: DesktopInstance, open_browser: bool) -> int:
    try:
        config.settings = config._load(require_model=False)
    except UserFacingError:
        config.settings = None
    app = create_app()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                access_log=False, proxy_headers=False, log_level="warning", log_config=None))
        app.state.shutdown = lambda: setattr(server, "should_exit", True)
        url = instance.publish(port, app.state.token)
        if open_browser:
            open_page(url)
        server.run(sockets=[sock])
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="رصام، دستیار دادهٔ شما")
    parser.add_argument("--no-browser", action="store_true", help="برای آزمون بدون بازکردن مرورگر")
    args = parser.parse_args(argv)
    try:
        if sys.platform == "darwin" and not args.no_browser:
            from rasam.desktop.macos import run
            return run(lambda: serve(True))
        return serve(not args.no_browser)
    except Exception as error:
        report = record_error(config.DATA_HOME, error)
        message = "راه‌اندازی برنامه کامل نشد؛ برنامه را دوباره باز کنید."
        if report:
            message += f"\nگزارش بررسی خطا: {report}"
        show_error(message)
        return 1


def show_error(message):
    import sys
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "رصام", 0x10)
    else:
        print(message)
