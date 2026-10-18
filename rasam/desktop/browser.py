"""در مک تب همان نشست را جلو می‌آوریم تا کلیک Dock کار کاربر را قطع نکند."""

import subprocess
import sys
import webbrowser
from urllib.parse import urlsplit


_CHROMIUM = {"com.google.Chrome", "com.microsoft.edgemac", "com.brave.Browser"}


def _mac_script(bundle: str, origin: str) -> str:
    # مقایسه با مبدأ، نه توکن یا مسیر: کاربر ممکن است به صفحهٔ اتصال رفته باشد.
    if bundle == "com.apple.Safari":
        select = "set current tab of w to t"
        minimize = "miniaturized"
    else:
        select = "set active tab index of w to tabIndex"
        minimize = "minimized"
    return f'''tell application id "{bundle}"
    repeat with w in windows
        set tabIndex to 0
        repeat with t in tabs of w
            set tabIndex to tabIndex + 1
            set address to URL of t
            if address is not missing value and (address starts with "{origin}/") then
                {select}
                set {minimize} of w to false
                set index of w to 1
                activate
                return "found"
            end if
        end repeat
    end repeat
    return "missing"
end tell'''


def _default_mac_browser(url: str) -> str | None:
    from AppKit import NSWorkspace
    from Foundation import NSBundle, NSURL

    app = NSWorkspace.sharedWorkspace().URLForApplicationToOpenURL_(NSURL.URLWithString_(url))
    return NSBundle.bundleWithURL_(app).bundleIdentifier() if app else None


def focus_existing(url: str) -> bool:
    """خطا یا مرورگر پشتیبانی‌نشده مانع بازکردن معمولی برنامه نمی‌شود."""
    if sys.platform != "darwin":
        return False
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "http" or parts.hostname != "127.0.0.1" or not port:
        return False
    bundle = _default_mac_browser(url)
    if bundle not in _CHROMIUM and bundle != "com.apple.Safari":
        return False
    origin = f"http://127.0.0.1:{parts.port}"
    try:
        result = subprocess.run(["/usr/bin/osascript", "-"], input=_mac_script(bundle, origin),
                                text=True, capture_output=True, timeout=5, check=False)
        return result.returncode == 0 and result.stdout.strip() == "found"
    except (OSError, subprocess.TimeoutExpired):
        return False


def open_page(url: str) -> None:
    if not focus_existing(url):
        webbrowser.open(url)
