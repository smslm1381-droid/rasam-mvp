"""خواندن پروفایل مشتری بدون نگه‌داشتن راز یا connection string در آن.

هر مشتری یک پوشه دارد: `customers/<نام>/`. `profile.yaml` می‌گوید چه دیتابیسی
دارد و چه قابلیت‌هایی می‌گیرد؛ بقیه‌ی فایل‌های همان پوشه دانش دامنه‌ی اوست.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ProfileError(ValueError):
    """پروفایل مشتری ساختار لازم را ندارد."""


@dataclass(frozen=True)
class CustomerProfile:
    name: str
    # پوشه‌ی مشتری. هر فایل مخصوص این مشتری (دانش، سوالات طلایی) از اینجا
    # خوانده می‌شود، تا هیچ مسیری در کد برای یک مشتری خاص ننشیند.
    directory: Path
    db_type: str
    connection_env: str
    allowed_collections: frozenset[str]
    capabilities: frozenset[str]
    limits: dict[str, int | None]


def load_profile(name: str, directory: Path) -> CustomerProfile:
    """پروفایل نام‌گذاری‌شده را از پوشه‌ی مشتریان می‌خواند."""
    path = directory / name / "profile.yaml"
    if not path.is_file():
        raise ProfileError(f"پروفایل مشتری «{name}» پیدا نشد: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ProfileError(f"پروفایل مشتری «{name}» باید یک شیء YAML باشد.")
    return _parse_profile(name, path.parent, data)


def _parse_profile(name: str, directory: Path, data: dict[str, Any]) -> CustomerProfile:
    required = ("db_type", "connection_env", "allowed_collections", "capabilities")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ProfileError(f"پروفایل «{name}» این بخش‌ها را ندارد: {', '.join(missing)}")
    limits = data.get("limits") or {}
    if not isinstance(limits, dict):
        raise ProfileError(f"بخش limits در پروفایل «{name}» باید شیء باشد.")
    parsed_limits = {key: _limit(value, name, key) for key, value in limits.items()}
    return CustomerProfile(
        name=name,
        directory=directory,
        db_type=_text(data["db_type"], name, "db_type"),
        connection_env=_text(data["connection_env"], name, "connection_env"),
        allowed_collections=_names(data["allowed_collections"], name, "allowed_collections"),
        capabilities=_names(data["capabilities"], name, "capabilities"),
        limits=parsed_limits,
    )


def _text(value: Any, name: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{field} در پروفایل «{name}» باید متن باشد.")
    return value.strip()


def _names(value: Any, name: str, field: str) -> frozenset[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProfileError(f"{field} در پروفایل «{name}» باید فهرست متن باشد.")
    names = frozenset(item.strip() for item in value if item.strip())
    if not names:
        raise ProfileError(f"{field} در پروفایل «{name}» نباید خالی باشد.")
    return names


def _limit(value: Any, name: str, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ProfileError(f"{field} در limits پروفایل «{name}» باید عدد مثبت باشد.")
    return value
