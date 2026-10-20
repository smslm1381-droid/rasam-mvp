"""مقصد اتصال را مدیر کل تأیید می‌کند؛ مدیر سازمان نمی‌تواند سرویس‌های داخلی میزبان را کاوش کند."""

import ipaddress
import socket
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from organization_portal.errors import PortalError

MONGO_OPTIONS = {"authsource", "replicaset", "directconnection", "retryreads", "retrywrites",
                 "appname", "readpreference", "authmechanism", "tls"}


def connection_uri(db_type, values, advanced=""):
    if db_type not in {"mongodb", "mysql"}:
        raise PortalError("نوع دیتابیس پشتیبانی نمی‌شود.")
    if advanced.strip():
        uri = advanced.strip()
    else:
        host = values.get("host", "").strip()
        if not host or any(char in host for char in "/@?# "):
            raise PortalError("آدرس سرور معتبر نیست.")
        if ":" in host and not host.startswith("["):
            host = "[" + host + "]"
        port = int(values.get("port") or (27017 if db_type == "mongodb" else 3306))
        uri = (f"{db_type}://{quote(values.get('username', ''), safe='')}:{quote(values.get('password', ''), safe='')}"
               f"@{host}:{port}/{quote(values.get('database', ''), safe='')}")
    return secure_uri(db_type, uri)


def secure_uri(db_type, uri):
    try:
        parts = urlsplit(uri)
        schemes = {"mongodb", "mongodb+srv"} if db_type == "mongodb" else {"mysql", "mariadb"}
        if len(uri) > 4096 or parts.scheme not in schemes or not parts.hostname or not parts.username or not parts.password or parts.fragment:
            raise ValueError()
        if "," in parts.netloc or parts.port is not None and not 1 <= parts.port <= 65535:
            raise ValueError()
        if parts.scheme == "mongodb+srv" and parts.port is not None:
            raise ValueError()
        options = {}
        for key, value in parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True):
            normalized = key.lower()
            allowed = MONGO_OPTIONS if db_type == "mongodb" else {"tls", "ssl_mode"}
            if normalized in options or normalized not in allowed:
                raise ValueError()
            if normalized == "tls" and value.lower() != "true":
                raise ValueError()
            if normalized == "ssl_mode" and value.upper() != "VERIFY_IDENTITY":
                raise ValueError()
            options[normalized] = (key, value)
        options["tls"] = ("tls", "true")
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(list(options.values())), ""))
    except (TypeError, ValueError):
        raise PortalError("نشانی اتصال معتبر نیست؛ TLS با بررسی گواهی الزامی است و گزینهٔ ناامن پذیرفته نمی‌شود.") from None


def check_destination(uri, allowed_hosts, local=False):
    try:
        parts = urlsplit(uri)
        host = parts.hostname.casefold().rstrip(".")
        port = parts.port or (27017 if parts.scheme.startswith("mongodb") else 3306)
        permitted = {value.casefold().rstrip(".") for value in allowed_hosts}
        if host not in permitted and f"{host}:{port}" not in permitted:
            raise PortalError("این مقصد برای سازمان تأیید نشده؛ مدیر کل باید آدرس مجاز را تعیین کند.", 403)
        addresses = resolve_addresses(parts.scheme, host, port)
        for entry in addresses:
            address = ipaddress.ip_address(entry[4][0])
            if address.is_unspecified or address.is_link_local or address.is_multicast or address.is_loopback and not local:
                raise PortalError("اتصال به این مقصد داخلی میزبان مجاز نیست.", 403)
    except PortalError:
        raise
    except (OSError, TypeError, ValueError):
        raise PortalError("مقصد پیدا نشد؛ DNS، مسیر خصوصی یا تونل سازمان را بررسی کنید.", 503) from None


def resolve_addresses(scheme, host, port):
    if scheme != "mongodb+srv":
        return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    import dns.exception
    import dns.resolver
    try:
        records = list(dns.resolver.resolve("_mongodb._tcp." + host, "SRV", lifetime=5))
        if not records or len(records) > 20:
            raise ValueError()
        addresses = []
        parent = host.split(".", 1)[-1]
        for record in records:
            target = str(record.target).rstrip(".").casefold()
            if not target.endswith("." + parent):
                raise ValueError()
            addresses.extend(socket.getaddrinfo(target, record.port, type=socket.SOCK_STREAM))
        return addresses
    except dns.exception.DNSException:
        raise OSError() from None


def identity(uri, database):
    parts = urlsplit(uri)
    return [parts.scheme, parts.hostname, parts.port, parts.username, database]
