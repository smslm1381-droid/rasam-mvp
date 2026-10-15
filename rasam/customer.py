"""خواندن پروفایل مشتری بدون نگه‌داشتن راز یا connection string در آن.

هر مشتری یک پوشه دارد: `customers/<نام>/`. `profile.yaml` می‌گوید چه دیتابیسی
دارد و چه قابلیت‌هایی می‌گیرد؛ بقیه‌ی فایل‌های همان پوشه دانش دامنه‌ی اوست.

این بارگذار **سخت‌گیر** است، چون پروفایل را آدم می‌نویسد و اشتباه آدم نباید
بی‌صدا اثر کند: `max_row` غلط‌املایی نباید سقف رکورد را خاموش بگذارد، و رمز نباید
هیچ‌وقت در مخزن بنشیند. هر چیزی که نشناسد خطای فارسی روشن می‌دهد.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Any

import yaml

# --- آنچه پروفایل اجازه دارد بگوید -------------------------------------------

KNOWN_FIELDS = ("db_type", "connection_env", "allowed_sources", "capabilities", "limits")
REQUIRED_FIELDS = ("db_type", "connection_env", "allowed_sources", "capabilities")
KNOWN_LIMITS = ("max_rows", "max_attempts")

# قابلیت یعنی چیزی که مشتری می‌تواند نداشته باشد.
KNOWN_CAPABILITIES = frozenset({"summary", "repair", "chart", "export_csv", "export_excel"})

# مراحل هسته. قابلیت نیستند و خاموش نمی‌شوند: گارد هرگز یک گزینه نیست
# (قاعده‌ی امنیتی ۳). نامشان در پروفایل، چه به‌عنوان قابلیت چه به‌عنوان فیلد،
# خطای جداگانه دارد تا کسی فکر نکند فقط «ناشناخته» است.
CORE_STEPS = frozenset({"prepare", "generate", "validate", "execute"})

# فقط **نام** متغیر محیطی؛ مثل `MONGO_URI`. چیزی که شبیه مقدار باشد، این الگو را نمی‌گذراند.
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")

# شکل رشته‌ی اتصال (`mongodb://`، `postgresql://`، `mongodb+srv://`، …) یا
# جفت «رمز = مقدار». عمداً گسترده است: پروفایل هیچ دلیلی برای داشتن URL ندارد.
_SECRET_SHAPES = (
    re.compile(r"[a-z][a-z0-9+.\-]*://", re.IGNORECASE),
    re.compile(r"(password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]", re.IGNORECASE),
)


class ProfileError(ValueError):
    """پروفایل مشتری معتبر نیست."""


@dataclass(frozen=True)
class CustomerProfile:
    name: str
    # پوشه‌ی مشتری. هر فایل مخصوص این مشتری (دانش، سوالات طلایی) از اینجا
    # خوانده می‌شود، تا هیچ مسیری در کد برای یک مشتری خاص ننشیند.
    directory: Path
    db_type: str
    connection_env: str
    allowed_sources: frozenset[str]
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
    # راز اول بررسی می‌شود: رشته‌ی اتصالی که در یک فیلد ناشناخته افتاده باشد
    # باید پیام «رمز» بگیرد، نه «فیلد ناشناخته».
    _reject_secrets(data, name)
    _reject_unknown(data, KNOWN_FIELDS, name, "پروفایل")

    missing = [key for key in REQUIRED_FIELDS if not data.get(key)]
    if missing:
        raise ProfileError(f"پروفایل «{name}» این بخش‌ها را ندارد: {', '.join(missing)}")

    return CustomerProfile(
        name=name,
        directory=directory,
        db_type=_text(data["db_type"], name, "db_type"),
        connection_env=_env_name(data["connection_env"], name),
        allowed_sources=_names(data["allowed_sources"], name, "allowed_sources"),
        capabilities=_capabilities(data["capabilities"], name),
        limits=_limits(data.get("limits"), name),
    )


# --- راز --------------------------------------------------------------------

def _strings(node: Any, path: str) -> Iterator[tuple[str, str]]:
    """همه‌ی مقدارهای متنی پروفایل، با مسیرشان (مثلاً `allowed_sources[2]`)."""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _strings(value, f"{path}[{index}]")


def _reject_secrets(data: dict[str, Any], name: str) -> None:
    """مقداری که شبیه رشته‌ی اتصال یا رمز باشد خطاست.

    خودِ مقدار در پیام **نمی‌آید**: اگر واقعاً رمز باشد، خطا نباید آن را در
    ترمینال و لاگ بریزد.
    """
    for path, value in _strings(data, ""):
        if any(shape.search(value) for shape in _SECRET_SHAPES):
            raise ProfileError(
                f"مقدار «{path}» در پروفایل «{name}» شبیه رشته‌ی اتصال یا رمز است. "
                "رمز هرگز در پروفایل نوشته نمی‌شود؛ آن را در `.env` بگذارید و فقط "
                "نام متغیر را در `connection_env` بنویسید."
            )


# --- فیلدها -----------------------------------------------------------------

def _reject_unknown(data: dict[str, Any], known: tuple[str, ...], name: str, where: str) -> None:
    """کلید ناشناخته خطاست، با حدسِ «منظورتان این بود؟» برای غلط‌املایی."""
    for key in data:
        if key in CORE_STEPS:
            raise ProfileError(_core_step_message(key, name))
        if key not in known:
            hint = get_close_matches(str(key), known, n=1)
            tip = f" منظورتان «{hint[0]}» بود؟" if hint else ""
            raise ProfileError(f"«{key}» در {where} «{name}» شناخته‌شده نیست.{tip}")


def _core_step_message(step: str, name: str) -> str:
    return (
        f"«{step}» در پروفایل «{name}» جزو هسته است، نه قابلیت: همیشه اجرا می‌شود "
        "و خاموش‌کردنش ممکن نیست. گارد هرگز یک گزینه نیست."
    )


def _text(value: Any, name: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{field} در پروفایل «{name}» باید متن باشد.")
    return value.strip()


def _env_name(value: Any, name: str) -> str:
    text = _text(value, name, "connection_env")
    if not _ENV_NAME.match(text):
        raise ProfileError(
            f"connection_env در پروفایل «{name}» باید **نام** یک متغیر محیطی باشد "
            "(حروف بزرگ لاتین، عدد و _، مثل MONGO_URI)."
        )
    return text


def _names(value: Any, name: str, field: str) -> frozenset[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProfileError(f"{field} در پروفایل «{name}» باید فهرست متن باشد.")
    names = frozenset(item.strip() for item in value if item.strip())
    if not names:
        raise ProfileError(f"{field} در پروفایل «{name}» نباید خالی باشد.")
    return names


def _capabilities(value: Any, name: str) -> frozenset[str]:
    capabilities = _names(value, name, "capabilities")
    for capability in sorted(capabilities):
        if capability in CORE_STEPS:
            raise ProfileError(_core_step_message(capability, name))
        if capability not in KNOWN_CAPABILITIES:
            hint = get_close_matches(capability, KNOWN_CAPABILITIES, n=1)
            tip = f" منظورتان «{hint[0]}» بود؟" if hint else ""
            raise ProfileError(
                f"قابلیت «{capability}» در پروفایل «{name}» شناخته‌شده نیست.{tip} "
                f"قابلیت‌های مجاز: {', '.join(sorted(KNOWN_CAPABILITIES))}."
            )
    return capabilities


def _limits(value: Any, name: str) -> dict[str, int | None]:
    limits = value or {}
    if not isinstance(limits, dict):
        raise ProfileError(f"بخش limits در پروفایل «{name}» باید شیء باشد.")
    _reject_unknown(limits, KNOWN_LIMITS, name, "limits پروفایل")
    return {key: _limit(item, name, key) for key, item in limits.items()}


def _limit(value: Any, name: str, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ProfileError(f"{field} در limits پروفایل «{name}» باید عدد مثبت باشد.")
    return value
