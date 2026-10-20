"""فرم و خطای امن اتصال؛ پیام درایور هرگز به رابط فرستاده نمی‌شود."""

from dataclasses import dataclass
import socket
from urllib.parse import quote, urlsplit


@dataclass(frozen=True)
class ConnectionReport:
    ok: bool
    category: str
    message: str


MESSAGES = {
    "connected": "اتصال به دیتابیس برقرار شد.",
    "host": "سرور پیدا نشد؛ آدرس سرور را بررسی کنید.",
    "port": "درگاه بسته است؛ شمارهٔ درگاه و فایروال را بررسی کنید.",
    "credentials": "نام کاربری یا رمز پذیرفته نشد.",
    "database": "دیتابیس با این نام پیدا نشد یا اجازهٔ دیدن آن را ندارید.",
    "timeout": "زمان اتصال تمام شد؛ شبکه و دسترسی سرور را بررسی کنید.",
    "invalid": "اطلاعات اتصال معتبر نیست؛ آدرس، درگاه و نام دیتابیس را بررسی کنید.",
    "connection": "اتصال برقرار نشد؛ تنظیمات امنیتی سرور و دسترسی را بررسی کنید.",
    "tls": "اتصال امن برقرار نشد؛ فعال‌بودن TLS، گواهی معتبر و نام میزبان را بررسی کنید.",
}


def report(category):
    return ConnectionReport(category == "connected", category, MESSAGES[category])


def fields(port):
    return [
        {"name": "host", "label": "آدرس سرور", "type": "text", "default": ""},
        {"name": "port", "label": "درگاه", "type": "number", "default": str(port)},
        {"name": "username", "label": "نام کاربری", "type": "text", "default": ""},
        {"name": "password", "label": "رمز", "type": "password", "default": ""},
        {"name": "database", "label": "نام دیتابیس", "type": "text", "default": ""},
    ]


def build_uri(scheme, values, default_port):
    host = values.get("host", "").strip()
    port = int(values.get("port") or default_port)
    if not host or any(char in host for char in "/@?#") or not 1 <= port <= 65535:
        raise ValueError(MESSAGES["invalid"])
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    username = quote(values.get("username", ""), safe="")
    password = quote(values.get("password", ""), safe="")
    database = quote(values.get("database", "").strip(), safe="")
    if not username or not database:
        raise ValueError(MESSAGES["invalid"])
    return f"{scheme}://{username}:{password}@{host}:{port}/{database}"


def preflight(uri, default_port):
    """خطای شبکه را پیش از درایور دسته‌بندی می‌کند؛ هیچ نوشتنی انجام نمی‌شود."""
    try:
        parts = urlsplit(uri)
        if not parts.hostname:
            return report("invalid")
        with socket.create_connection((parts.hostname, parts.port or default_port), timeout=3):
            return None
    except socket.gaierror:
        return report("host")
    except (TimeoutError, socket.timeout):
        return report("timeout")
    except ConnectionRefusedError:
        return report("port")
    except ValueError:
        return report("invalid")
    except OSError:
        return report("connection")
