"""بررسی آمادگی تحویل: «این مشتری آماده است یا نه، و اگر نه، چرا».

با مدل تماس نمی‌گیرد، پس سریع و رایگان است و هر چند بار لازم باشد اجرا می‌شود.
اجرای سنجه‌ی کیفیت (`scripts/evaluate.py`) یک قلم جداست، چون هزینه و سهمیه دارد.

هر بررسی یک `Check` برمی‌گرداند — مقدار، نه استثنا. متن خطای دیتابیس هرگز عیناً
نمی‌آید (ممکن است نشانی سرور یا رمز را بازتاب دهد)؛ فقط نوع خطا.

بررسی روی **پوشه‌ی نام‌داده‌شده** انجام می‌شود، نه مشتری فعال: ایجنت با اتصال و
فهرست سفید همان مشتری ساخته می‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rasam import config, console, customer
from rasam.databases import registry

MIN_GOLDEN_QUESTIONS = 10
GOLDEN_SHAPES = ("value", "empty", "message")


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


def _load_profile(name: str, directory: Path) -> tuple[Check, customer.CustomerProfile | None]:
    try:
        profile = customer.load_profile(name, directory)
    except customer.ProfileError as error:
        return Check("پروفایل معتبر و بدون راز", False, str(error)), None
    if profile.db_type not in registry.AGENTS:
        known = ", ".join(sorted(registry.AGENTS))
        return Check("پروفایل معتبر و بدون راز", False,
                     f"نوع دیتابیس «{profile.db_type}» آداپتور ندارد (موجود: {known})."), None
    return Check("پروفایل معتبر و بدون راز", True, f"نوع دیتابیس: {profile.db_type}"), profile


def _build_agent(profile: customer.CustomerProfile):
    """ایجنت با اتصال و فهرست سفیدِ **همین مشتری**. مقدار اتصال هرگز چاپ نمی‌شود."""
    return registry.AGENTS[profile.db_type](
        connection_uri=config.secret_value(profile.connection_env),
        database=profile.database,
        allowed_sources=profile.allowed_sources,
    )


def _connection(profile: customer.CustomerProfile, agent) -> tuple[Check, list[str] | None]:
    name = "متغیر اتصال و برقراری اتصال"
    variable = f"{config.ENV_PREFIX}{profile.connection_env}"
    if config.secret_value(profile.connection_env) is None:
        return Check(name, False, f"متغیر {variable} در `.env` یا محیط نیست."), None
    try:
        return Check(name, True, f"{variable} هست و وصل شد."), agent.list_sources()
    except Exception as error:  # noqa: BLE001 — پیام خطا ممکن است نشانی یا رمز را بازتاب دهد
        return Check(name, False, f"اتصال ناموفق بود ({type(error).__name__})."), None


def _read_only(agent, connected: bool) -> Check:
    name = "کاربر دیتابیس فقط-خواندنی است"
    if not connected:
        return Check(name, False, "تا اتصال برقرار نشود بررسی نمی‌شود.")
    try:
        report = agent.check_read_only()
    except Exception as error:  # noqa: BLE001
        return Check(name, False, f"بررسی دسترسی‌ها شکست خورد ({type(error).__name__}).")
    return Check(name, report.read_only, report.detail)


def _sources_exist(profile: customer.CustomerProfile, existing: list[str] | None) -> Check:
    name = "همه‌ی منابع مجاز واقعاً وجود دارند"
    if existing is None:
        return Check(name, False, "تا اتصال برقرار نشود بررسی نمی‌شود.")
    missing = sorted(profile.allowed_sources - set(existing))
    if missing:
        return Check(name, False, f"در دیتابیس نیستند: {', '.join(missing)}")
    return Check(name, True, f"{len(profile.allowed_sources)} منبع.")


def _row_cap(profile: customer.CustomerProfile) -> Check:
    name = "سقف رکورد روشن است"
    cap = profile.limits.get("max_rows")
    if cap is None:
        return Check(name, False, "limits.max_rows در پروفایل نیست؛ تحویل با سقف خاموش ممکن نیست.")
    return Check(name, True, f"max_rows = {cap}")


def _documentation(profile: customer.CustomerProfile) -> Check:
    name = "دانش دامنه کامل است"
    path = profile.directory / "documentation.md"
    if not path.is_file() or not console.read_text(path).strip():
        return Check(name, False, "documentation.md نیست یا خالی است.")
    left = [
        file.name for file in sorted(profile.directory.iterdir())
        if file.is_file() and customer.TODO_MARKER in console.read_text(file)
    ]
    if left:
        return Check(name, False, f"{customer.TODO_MARKER} هنوز مانده در: {', '.join(left)}")
    return Check(name, True, "جای خالی باقی نمانده.")


def _yaml_list(path: Path) -> list[Any] | None:
    if not path.is_file():
        return []
    data = yaml.safe_load(console.read_text(path))
    return data if isinstance(data, list) else None


def _examples(profile: customer.CustomerProfile, agent) -> Check:
    """هر نمونه مستقیم به مدل یاد می‌دهد چه بنویسد؛ نمونه‌ی ردشدنی یعنی آموزش بن‌بست (تصمیم ۳۵)."""
    name = "همه‌ی نمونه‌ها از گارد رد می‌شوند"
    examples = _yaml_list(profile.directory / "examples.yaml")
    if examples is None:
        return Check(name, False, "examples.yaml باید فهرست باشد.")
    for index, example in enumerate(examples, start=1):
        try:
            result = agent.validate_query(example["source"], example["query"])
        except (KeyError, TypeError):
            return Check(name, False, f"نمونه‌ی {index} کلیدهای source و query را ندارد.")
        if not result.ok:
            return Check(name, False, f"نمونه‌ی {index} رد شد: {result.reason}")
    return Check(name, True, f"{len(examples)} نمونه.")


def _golden(profile: customer.CustomerProfile) -> Check:
    name = f"دست‌کم {MIN_GOLDEN_QUESTIONS} سوال طلایی"
    questions = _yaml_list(profile.directory / "golden_questions.yaml")
    if questions is None:
        return Check(name, False, "golden_questions.yaml باید فهرست باشد.")
    valid = [q for q in questions if isinstance(q, dict) and q.get("question")
             and isinstance(q.get("expect"), dict)
             and any(shape in q["expect"] for shape in GOLDEN_SHAPES)]
    if len(valid) < MIN_GOLDEN_QUESTIONS:
        return Check(name, False, f"{len(valid)} سوال معتبر هست.")
    return Check(name, True, f"{len(valid)} سوال.")


def run_checks(name: str, directory: Path | None = None) -> list[Check]:
    """همه‌ی بررسی‌ها برای مشتریِ `name`، به ترتیب نمایش."""
    profile_check, profile = _load_profile(name, directory or config.CUSTOMERS_DIR)
    if profile is None:
        return [profile_check, Check("بقیه‌ی بررسی‌ها", False, "تا پروفایل معتبر نشود انجام نمی‌شوند.")]

    try:
        agent = _build_agent(profile)
        connection, sources = _connection(profile, agent)
    except Exception:
        return [profile_check, Check("اتصال", False, "اطلاعات اتصال یا انبار امن رمز در دسترس نیست.")]
    return [
        profile_check,
        connection,
        _read_only(agent, sources is not None),
        _sources_exist(profile, sources),
        _row_cap(profile),
        _documentation(profile),
        _examples(profile, agent),
        _golden(profile),
    ]


def render(checks: list[Check]) -> str:
    return "\n".join(f"{'✅' if c.ok else '❌'} {c.name}" + (f" — {c.detail}" if c.detail else "")
                     for c in checks)
