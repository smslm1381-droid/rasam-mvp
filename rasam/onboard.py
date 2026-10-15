"""ابزار تحویل مشتری: `python onboard.py new`.

مشتری تازه که می‌آید، این ابزار چند سوال ساده می‌پرسد — **اول از همه نوع
دیتابیسش** — و پوشه‌ی `customers/<نام>/` را متناسب با همان دیتابیس می‌چیند.

سه قاعده‌ی این فایل:

- **رشته‌ی اتصال هرگز پرسیده، چاپ یا نوشته نمی‌شود** (تصمیم ۶۸). فقط *نام*
  متغیر محیطی پرسیده می‌شود و وجودش چک می‌شود؛ مقدارش مستقیم به ایجنت می‌رود.
- **دانش دامنه حدس زده نمی‌شود.** ابزار فهرست منابع و فیلدها را می‌نویسد و جای
  خالی «واژه‌ی فارسی / توضیح / تله» را با `TODO(onboarding)` علامت می‌زند.
  پرکردنش کار آدم است، با خود مشتری.
- **فهرست سفید پیش‌فرض خالی است**، نه «همه». منبعی که کسی انتخابش نکرده نه
  توصیف می‌شود نه خوانده (تصمیم‌های ۳۰ و ۵۲).

ورودی و خروجی از بیرون تزریق می‌شوند (`ask`، `say`) تا همه‌ی مسیر بدون ترمینال
قابل آزمون باشد.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from pathlib import Path
from string import Template

from rasam import config, customer
from rasam.databases import registry

TEMPLATES_DIR = config.PROJECT_ROOT / "templates" / "customer"
TEMPLATE_FILES = ("profile.yaml", "documentation.md", "examples.yaml",
                  "field_notes.yaml", "golden_questions.yaml")

# نشانه‌ای که ابزار در هر جای خالیِ دانش می‌گذارد. بررسی آمادگی تحویل (`check`)
# تا یکی از این‌ها مانده باشد قرمز می‌ماند.
TODO_MARKER = "TODO(onboarding)"

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

Ask = Callable[[str], str]
Say = Callable[[str], None]


def _ask_name(ask: Ask, say: Say) -> str | None:
    name = ask("نام مشتری (حروف کوچک لاتین، عدد و خط تیره، مثل acme-solar): ").strip()
    if not NAME_RE.match(name):
        say("نام نامعتبر است: با حرف کوچک لاتین شروع شود و فقط حرف کوچک، عدد و - داشته باشد.")
        return None
    if (config.CUSTOMERS_DIR / name).exists():
        say(f"مشتری «{name}» از قبل هست: {config.CUSTOMERS_DIR / name}. چیزی بازنویسی نشد.")
        return None
    return name


def _ask_db_type(ask: Ask, say: Say) -> str | None:
    """نوع دیتابیس — منو فقط از آداپتورهای ثبت‌شده در رجیستری."""
    types = sorted(registry.AGENTS)
    say("نوع دیتابیس مشتری:")
    for number, db_type in enumerate(types, start=1):
        say(f"  {number}. {db_type}")
    say("  اگر دیتابیس مشتری در این فهرست نیست، اول باید برایش آداپتور نوشته شود: "
        "docs/adding-a-database.md")
    answer = ask("شماره یا نام: ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(types):
        return types[int(answer) - 1]
    if answer in types:
        return answer
    say(f"«{answer}» در فهرست نیست.")
    return None


def _ask_connection_env(ask: Ask, say: Say, name: str) -> str | None:
    """**نام** متغیر اتصال را می‌پرسد و فقط وجودش را چک می‌کند."""
    default = name.upper().replace("-", "_") + "_DB_URI"
    variable = ask(f"نام متغیر محیطی اتصال [{default}]: ").strip() or default
    if not ENV_RE.match(variable):
        say("نام متغیر باید حروف بزرگ لاتین، عدد و _ باشد (مثل ACME_DB_URI).")
        return None
    if config.env_value(variable) is None:
        say(f"متغیر {config.ENV_PREFIX}{variable} در `.env` نیست.\n"
            f"رشته‌ی اتصال **فقط-خواندنی** مشتری را با همین نام در `.env` بگذارید و دوباره اجرا کنید.\n"
            "(این ابزار رشته‌ی اتصال را نمی‌پرسد و هرگز جایی نمی‌نویسد.)")
        return None
    return variable


def _choose_sources(sources: list[str], ask: Ask, say: Say) -> list[str] | None:
    """مجازها را انسان انتخاب می‌کند؛ پیش‌فرض هیچ‌کدام است."""
    if not sources:
        say("این دیتابیس هیچ کالکشن یا جدولی ندارد یا کاربر دسترسی خواندنشان را ندارد.")
        return None
    say("منابع دیتابیس:")
    for number, source in enumerate(sources, start=1):
        say(f"  {number}. {source}")
    say("فقط منابعی را انتخاب کنید که پاسخ به سوال لازم دارند. جدول‌های حساس "
        "(کاربران، صورت‌حساب، لاگ) را **انتخاب نکنید**.")
    answer = ask("شماره‌ها با کاما (مثل 1,3): ").strip()
    try:
        picked = sorted({int(part) for part in answer.split(",") if part.strip()})
    except ValueError:
        picked = []
    if not picked or not all(1 <= number <= len(sources) for number in picked):
        say("هیچ منبع معتبری انتخاب نشد؛ چیزی ساخته نشد.")
        return None
    return [sources[number - 1] for number in picked]


def _render(template: str, **values: str) -> str:
    return Template((TEMPLATES_DIR / template).read_text(encoding="utf-8")).safe_substitute(values)


def _sources_block(agent, sources: list[str]) -> str:
    """برای هر منبع یک بند با نام فیلدهایش و جای خالی توضیح."""
    blocks = []
    for source in sources:
        fields = ", ".join(f"`{field}`" for field in agent.list_fields(source))
        blocks.append(f"- `{source}` — {TODO_MARKER}: what it holds, and the Persian word "
                      f"users say for it.\n  Fields: {fields}")
    return "\n".join(blocks)


def _write_customer(name: str, db_type: str, connection_env: str, database: str,
                    sources: list[str], agent) -> Path:
    folder = config.CUSTOMERS_DIR / name
    folder.mkdir(parents=True)
    try:
        values = {
            "name": name, "db_type": db_type, "connection_env": connection_env,
            "database": database,
            "sources": "\n".join(f"  - {source}" for source in sources),
            "sources_block": _sources_block(agent, sources),
        }
        for template in TEMPLATE_FILES:
            (folder / template).write_text(_render(template, **values), encoding="utf-8")
        customer.load_profile(name, config.CUSTOMERS_DIR)  # خودآزمایی: پروفایل ساخته‌شده معتبر است
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)  # نیمه‌کاره نماند
        raise
    return folder


def run_new(ask: Ask = input, say: Say = print) -> int:
    """زیرفرمان `new`. کد خروج: ۰ موفق، ۱ منصرف‌شده یا ناموفق."""
    name = _ask_name(ask, say)
    if name is None:
        return 1
    db_type = _ask_db_type(ask, say)
    if db_type is None:
        return 1
    connection_env = _ask_connection_env(ask, say, name)
    if connection_env is None:
        return 1
    database = ask("نام دیتابیس: ").strip()
    if not database:
        say("نام دیتابیس خالی است.")
        return 1

    agent = registry.AGENTS[db_type](
        connection_uri=config.env_value(connection_env), database=database)
    try:
        available = agent.list_sources()
    except Exception as error:  # noqa: BLE001 — پیام خطا ممکن است نشانی سرور را داشته باشد؛ فقط نوعش
        say(f"اتصال یا خواندن فهرست منابع ناموفق بود ({type(error).__name__}). "
            "رشته‌ی اتصال، نام دیتابیس و دسترسی کاربر را بررسی کنید.")
        return 1

    sources = _choose_sources(available, ask, say)
    if not sources:
        return 1
    try:
        folder = _write_customer(name, db_type, connection_env, database, sources, agent)
    except Exception as error:  # noqa: BLE001 — خواندن فیلدها هم می‌تواند شکست بخورد
        say(f"ساختن پوشه‌ی مشتری ناموفق بود ({type(error).__name__}) و چیزی باقی نماند.")
        return 1

    say(f"\nپوشه‌ی مشتری ساخته شد: {folder}\nقدم‌های بعد:\n"
        f"  ۱. همه‌ی {TODO_MARKER}های documentation.md را با خود مشتری پر کنید.\n"
        "  ۲. نمونه‌ها (examples.yaml) و دست‌کم ۱۰ سوال طلایی (golden_questions.yaml) بنویسید.\n"
        f"  ۳. `RASAM_CUSTOMER={name}` را در `.env` بگذارید و یک سوال بپرسید.\n"
        f"  ۴. `python onboard.py check {name}` را اجرا کنید.")
    return 0


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="ابزار تحویل مشتری رصام")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("new", help="ساختن پوشه‌ی مشتری تازه")
    args = parser.parse_args(argv)
    return run_new() if args.command == "new" else 1
