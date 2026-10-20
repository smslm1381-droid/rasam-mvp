"""TLS انتخاب‌شده باید گواهی و نام میزبان را بررسی کند و به اتصال ساده برنگردد."""

import ssl
from urllib.parse import parse_qsl

import pymysql
from pymysql.constants import CLIENT


def options(query):
    if not query:
        return {}
    values = {}
    for name, value in parse_qsl(query, keep_blank_values=True, strict_parsing=True):
        name = name.lower()
        if name in values or name not in {"tls", "tlscafile", "ssl_ca", "ssl_mode"}:
            raise ValueError("گزینهٔ اتصال MySQL ناشناخته یا تکراری است.")
        values[name] = value
    enabled = values.get("tls", "").lower()
    mode = values.get("ssl_mode", "").upper()
    if enabled not in {"", "true", "false"} or mode not in {"", "VERIFY_IDENTITY", "DISABLED"}:
        raise ValueError("TLS باید با بررسی گواهی و نام میزبان تنظیم شود.")
    if enabled == "false" and mode == "VERIFY_IDENTITY" or enabled == "true" and mode == "DISABLED":
        raise ValueError("تنظیمات TLS با هم سازگار نیستند.")
    if "tlscafile" in values and "ssl_ca" in values:
        raise ValueError("فایل مرجع گواهی را فقط یک بار تعیین کنید.")
    ca = values.get("tlscafile", values.get("ssl_ca", ""))
    required = enabled == "true" or mode == "VERIFY_IDENTITY"
    if ca and not required:
        raise ValueError("برای تعیین مرجع گواهی، TLS را فعال کنید.")
    if not required:
        return {"ssl_disabled": True} if enabled == "false" or mode == "DISABLED" else {}
    context = ssl.create_default_context(cafile=ca or None)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return {"ssl": context}


class VerifiedConnection(pymysql.connections.Connection):
    def _request_authentication(self):
        # بررسی پیش از ارسال رمز است؛ بعضی نسخه‌های درایور TLS را اختیاری می‌گیرند.
        if not self.server_capabilities & CLIENT.SSL:
            raise pymysql.OperationalError(2026, "TLS is required")
        return super()._request_authentication()
