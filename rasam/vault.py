"""رازها فقط به انبار رمز سیستم‌عامل سپرده می‌شوند؛ جایگزین فایل متنی نداریم."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import keyring

SERVICE = "Rasam"
NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
SECURE_BACKENDS = (
    "keyring.backends.Windows", "keyring.backends.macOS",
    "keyring.backends.SecretService", "keyring.backends.kwallet",
)


@dataclass(frozen=True)
class Result:
    ok: bool
    value: str | None = field(default=None, repr=False)
    error: str | None = None


def _backend():
    backend = keyring.get_keyring()
    if type(backend).__module__ not in SECURE_BACKENDS:
        raise RuntimeError("unsupported backend")
    return backend


def _operate(action: str, name: str, value: str | None = None) -> Result:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        return Result(False, error="نام راز باید حروف بزرگ لاتین، عدد و زیرخط باشد.")
    if action == "set" and (not isinstance(value, str) or not value):
        return Result(False, error="مقدار راز خالی است و ذخیره نشد.")
    try:
        backend = _backend()
        if action == "get":
            return Result(True, value=backend.get_password(SERVICE, name))
        if action == "set":
            backend.set_password(SERVICE, name, value)
        elif backend.get_password(SERVICE, name) is not None:
            backend.delete_password(SERVICE, name)
        return Result(True)
    except Exception:  # خطای backend ممکن است خودِ راز را داشته باشد؛ هرگز بازتاب نمی‌دهیم.
        return Result(False, error="انبار امن رمز سیستم‌عامل در دسترس نیست؛ دوباره برنامه را باز کنید.")


def read_secret(name: str) -> Result:
    return _operate("get", name)


def write_secret(name: str, value: str) -> Result:
    return _operate("set", name, value)


def delete_secret(name: str) -> Result:
    return _operate("delete", name)
