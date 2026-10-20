"""رمز انسانی روی میزبان Python هش می‌شود؛ محدودیت Workers باعث ضعیف‌شدن هش نمی‌شود."""

import hashlib
import hmac
import re
import secrets

from organization_portal.errors import PortalError

ITERATIONS = 600000
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def email(value):
    value = value.strip().casefold()
    if len(value) > 254 or not EMAIL.fullmatch(value) or not value.isascii():
        raise PortalError("ایمیل معتبر وارد کنید.")
    return value


def encode(password):
    if not 12 <= len(password) <= 128:
        raise PortalError("رمز باید بین ۱۲ تا ۱۲۸ کاراکتر باشد.")
    salt = secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${value.hex()}"


def verify(password, encoded):
    try:
        name, count, salt, expected = encoded.split("$")
        if name != "pbkdf2_sha256" or int(count) != ITERATIONS or len(salt) != 32 or len(expected) != 64:
            return False
        value = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
        return hmac.compare_digest(value.hex(), expected)
    except (ValueError, TypeError):
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()
