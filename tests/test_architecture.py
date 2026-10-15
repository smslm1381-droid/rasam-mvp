"""تست معماری — مرز بین هسته، دیتابیس‌ها و مشتری‌ها را کد نگه می‌دارد، نه نیت خوب.

این سه تست از ماژولارکردن می‌آیند (تصمیم ۶۴): «سفارشی با پیکربندی، نه با کد»
فقط وقتی واقعی است که معلوم باشد هر چیز مال کدام لایه است. اگر یکی قرمز شد،
یعنی چیزی جای اشتباه نشسته؛ جابه‌جایش کن، نه تست را.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "rasam"
DATABASES = PACKAGE / "databases"

# درایور هر دیتابیس: فقط داخل پوشه‌ی آداپتور خودش. `scripts/` (پرکردن داده) بیرون
# از بسته‌ی `rasam/` است و عمداً در این بررسی نیست.
DRIVERS = {
    "pymongo": "mongodb",
    "bson": "mongodb",
    "pymysql": "mysql",
    # پارسر SQL: مشترک آداپتورهای SQL. فعلاً فقط mysql؛ آداپتور SQL بعدی اینجا اضافه می‌شود.
    "sqlglot": "mysql",
}

# تنها ماژول‌هایی از `databases/` که بیرون از آن مجازند.
SHARED_DATABASE_MODULES = {"rasam.databases.base", "rasam.databases.registry"}


def python_files(folder: Path):
    return sorted(path for path in folder.rglob("*.py") if "__pycache__" not in path.parts)


def is_module(dotted: str) -> bool:
    relative = Path(*dotted.split("."))
    return (ROOT / relative).with_suffix(".py").is_file() or (ROOT / relative / "__init__.py").is_file()


def imported_modules(path: Path) -> set[str]:
    """همه‌ی ماژول‌هایی که فایل import می‌کند، حتی داخل تابع (مثل psycopg در پستگرس)."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            # `from rasam.databases import registry` یعنی ماژول `rasam.databases.registry`؛
            # ولی `from rasam.databases.base import Result` یک نام است، نه ماژول.
            found.update(
                f"{node.module}.{alias.name}" for alias in node.names
                if is_module(f"{node.module}.{alias.name}"))
    return found


def owner(path: Path) -> str | None:
    """نوع دیتابیسی که این فایل متعلق به آن است، یا None اگر مشترک است."""
    relative = path.relative_to(DATABASES) if DATABASES in path.parents else None
    return relative.parts[0] if relative and len(relative.parts) > 1 else None


# --- ۱) هر درایور فقط در پوشه‌ی آداپتور خودش ----------------------------------

@pytest.mark.parametrize("path", python_files(PACKAGE), ids=lambda p: str(p.relative_to(ROOT)))
def test_a_database_driver_is_imported_only_inside_its_own_adapter(path):
    for module in imported_modules(path):
        driver = DRIVERS.get(module.split(".")[0])
        if driver:
            assert owner(path) == driver, (
                f"{path.relative_to(ROOT)} درایور «{module}» را import کرده، ولی این "
                f"درایور فقط داخل rasam/databases/{driver}/ مجاز است.")


# --- ۲) هسته هیچ دیتابیس خاصی را مستقیم نمی‌شناسد ------------------------------

def outside_databases():
    return [p for p in python_files(PACKAGE) if DATABASES not in p.parents]


@pytest.mark.parametrize("path", outside_databases(), ids=lambda p: str(p.relative_to(ROOT)))
def test_nothing_outside_databases_imports_a_specific_database(path):
    """هسته، تنظیمات و لایه‌های نمایش فقط از راه `registry` و `base` با دیتابیس حرف می‌زنند."""
    for module in imported_modules(path):
        if module.startswith("rasam.databases") and module not in {"rasam.databases", *SHARED_DATABASE_MODULES}:
            pytest.fail(
                f"{path.relative_to(ROOT)} ماژول «{module}» را مستقیم import کرده؛ "
                "فقط rasam.databases.registry و rasam.databases.base مجازند.")


# --- ۳) نام منبع هیچ مشتری‌ای در کد نمی‌نشیند ---------------------------------

def customer_source_names() -> set[str]:
    names: set[str] = set()
    for profile in (ROOT / "customers").glob("*/profile.yaml"):
        names.update(yaml.safe_load(profile.read_text(encoding="utf-8")).get("allowed_sources", []))
    return names


def string_values(path: Path):
    """رشته‌های داخل کد، بدون docstring — توضیح و مثال در docstring آزاد است."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.lineno, node.value


def test_there_are_customer_source_names_to_check_against():
    """بدون این، تست پایین هرگز چیزی نمی‌گیرد و بی‌صدا سبز می‌ماند."""
    assert "inverter_data" in customer_source_names()


@pytest.mark.parametrize("path", python_files(PACKAGE), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_customer_collection_or_table_name_appears_in_the_code(path):
    """همان نشتی که تصمیم ۶۲ بست: دانش یک مشتری باید در `customers/` بماند."""
    names = customer_source_names()
    for line, value in string_values(path):
        leaked = sorted(name for name in names if name in value)
        assert not leaked, f"{path.relative_to(ROOT)}:{line} نام منبع مشتری «{leaked[0]}» را در کد دارد."
