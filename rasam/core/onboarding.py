"""ساخت مشترک پوشهٔ مشتری؛ رابط و خط فرمان فقط ورودی را جمع می‌کنند."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from string import Template
import yaml

from rasam import config, customer
from rasam.databases import registry

TEMPLATES_DIR = config.PROJECT_ROOT / "templates" / "customer"
TEMPLATE_FILES = ("profile.yaml", "documentation.md", "examples.yaml", "field_notes.yaml", "golden_questions.yaml")
TODO_MARKER = customer.TODO_MARKER
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SENSITIVE_NAME = re.compile(r"user|account|billing|invoice|payment|secret|token|password|credential|auth|session|log|audit", re.IGNORECASE)


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
    if not NAME_RE.fullmatch(name) or folder.resolve().parent != config.CUSTOMERS_DIR.resolve():
        raise ValueError("نام مشتری معتبر نیست.")
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
        # نام جدول و دیتابیس داده‌اند؛ نباید با نویسهٔ YAML ساختار پروفایل را عوض کنند.
        profile = {"db_type": db_type, "connection_env": connection_env, "database": database,
                   "allowed_sources": sources, "capabilities": sorted(customer.KNOWN_CAPABILITIES),
                   "limits": {"max_rows": 1000, "max_attempts": 2}}
        (folder / "profile.yaml").write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
        customer.load_profile(name, config.CUSTOMERS_DIR)  # خودآزمایی: پروفایل ساخته‌شده معتبر است
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)  # نیمه‌کاره نماند
        raise
    return folder
