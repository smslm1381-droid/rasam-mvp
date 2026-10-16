"""سوکت پیش از انتخاب درگاه به سرور سپرده می‌شود تا فاصلهٔ آزادبودن و استفاده نداشته باشیم."""

from __future__ import annotations

import argparse
import socket
import webbrowser

import uvicorn

from rasam import config
from rasam.desktop.app import create_app
from rasam.errors import UserFacingError


def serve(open_browser: bool = True) -> int:
    try:
        config.settings = config._load()
    except UserFacingError:
        config.settings = None
    app = create_app()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        port = sock.getsockname()[1]
        if open_browser:
            webbrowser.open(f"http://127.0.0.1:{port}/?token={app.state.token}")
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                access_log=False, proxy_headers=False, log_level="warning"))
        server.run(sockets=[sock])
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="رصام، دستیار دادهٔ شما")
    parser.add_argument("--no-browser", action="store_true", help="برای آزمون بدون بازکردن مرورگر")
    args = parser.parse_args(argv)
    try:
        return serve(not args.no_browser)
    except OSError:
        print("راه‌اندازی سرور محلی انجام نشد؛ برنامه را دوباره باز کنید.")
        return 1
