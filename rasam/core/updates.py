"""بررسی نسخه فقط اطلاع می‌دهد؛ قطع اینترنت مانع استفاده از برنامه نمی‌شود."""

import re
from urllib.parse import urlsplit
import httpx

from rasam import __version__, desktop_service


def version_parts(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,5}\.\d{1,5}\.\d{1,5}", value):
        return None
    return tuple(int(part) for part in value.split("."))


def release_status(data, current):
    result = {"available": False, "current_version": current}
    if not isinstance(data, dict):
        return result
    latest = version_parts(data.get("version"))
    installed = version_parts(current)
    download = data.get("download_url")
    if not latest or not installed or latest <= installed or not isinstance(download, str):
        return result
    try:
        parts = urlsplit(download)
    except ValueError:
        return result
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or any(char.isspace() for char in download)):
        return result
    return {**result, "available": True, "version": data["version"], "download_url": download}


def check():
    unavailable = {"available": False, "current_version": __version__}
    url = desktop_service.gateway_url()
    if not url:
        return unavailable
    try:
        response = httpx.get(url + "/version", timeout=3, follow_redirects=False)
        if response.status_code != 200 or len(response.content) > 20000:
            return unavailable
        return release_status(response.json(), __version__)
    except Exception:
        return unavailable
