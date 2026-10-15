"""تست بررسی آمادگی تحویل: هر خرابی عمدی یک خط قرمز با توضیح فارسی.

مشتری آزمایشی از روی `customers/demo` در پوشه‌ی موقت ساخته می‌شود و به همان مونگوی
محلی وصل است؛ هر تست یک چیز را خراب می‌کند و فقط همان باید قرمز شود. اگر مونگو یا
اتصال مدیر در دسترس نیست، تست‌های وابسته با پیام روشن skip می‌شوند.
"""

from __future__ import annotations

import shutil

import pytest

from rasam import config, customer, onboard
from rasam.core import readiness

DEMO = config.CUSTOMERS_DIR / "demo"
VARIABLE = "READINESS_URI"


@pytest.fixture
def make(tmp_path, monkeypatch):
    """سازنده‌ی مشتری آزمایشی: کپی دمو، با تغییرهایی که تست می‌خواهد."""
    monkeypatch.setenv(f"RASAM_{VARIABLE}", config.settings.connection_uri)

    def build(**changes) -> str:
        folder = tmp_path / "cust"
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(DEMO, folder)
        profile = (folder / "profile.yaml").read_text(encoding="utf-8")
        profile = profile.replace("connection_env: MONGO_URI", f"connection_env: {VARIABLE}")
        for old, new in changes.get("profile", {}).items():
            assert old in profile, old
            profile = profile.replace(old, new)
        (folder / "profile.yaml").write_text(profile, encoding="utf-8")
        for name, text in changes.get("files", {}).items():
            (folder / name).write_text(text, encoding="utf-8")
        return "cust"

    return build


def results(name: str, tmp_path) -> dict[str, readiness.Check]:
    return {check.name: check for check in readiness.run_checks(name, tmp_path)}


def failed(name: str, tmp_path) -> list[str]:
    return [check.name for check in readiness.run_checks(name, tmp_path) if not check.ok]


@pytest.fixture(autouse=True)
def needs_mongo():
    from rasam.databases.mongodb import MongoAgent

    try:
        MongoAgent().list_sources()
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"مونگوی محلی در دسترس نیست: {type(error).__name__}")


def test_a_complete_customer_is_ready(make, tmp_path):
    assert failed(make(), tmp_path) == []


def test_the_real_demo_customer_is_ready():
    assert [c.name for c in readiness.run_checks("demo") if not c.ok] == []


# --- چهار خرابی عمدیِ معیار پذیرش -------------------------------------------

def test_red_when_a_connection_string_is_inside_the_profile(make, tmp_path):
    name = make(profile={f"connection_env: {VARIABLE}": "connection_env: 'mongodb://u:p@h/d'"})
    checks = readiness.run_checks(name, tmp_path)
    assert not checks[0].ok and "رمز" in checks[0].detail
    assert "p@h" not in readiness.render(checks)  # خودِ مقدار چاپ نمی‌شود


def test_red_when_the_database_user_can_write(make, tmp_path, monkeypatch):
    """کاربر مدیر (ساخته‌شده با اتصال ادمین محلی، تصمیم ۱۲) فقط-خواندنی نیست."""
    admin = config.settings.mongo_admin_uri
    if not admin:
        pytest.skip("RASAM_MONGO_ADMIN_URI در `.env` نیست.")
    name = make()
    monkeypatch.setenv(f"RASAM_{VARIABLE}", admin)
    checks = results(name, tmp_path)
    read_only = checks["کاربر دیتابیس فقط-خواندنی است"]
    assert not read_only.ok and "غیرخواندنی" in read_only.detail
    assert all(check.ok for key, check in checks.items() if key != read_only.name)


def test_red_when_an_allowed_source_does_not_exist(make, tmp_path):
    name = make(profile={"  - string_data": "  - string_data\n  - ghost_table"})
    check = results(name, tmp_path)["همه‌ی منابع مجاز واقعاً وجود دارند"]
    assert not check.ok and "ghost_table" in check.detail


def test_red_when_the_row_cap_is_off(make, tmp_path):
    name = make(profile={"  max_rows: 1000\n": ""})
    check = results(name, tmp_path)["سقف رکورد روشن است"]
    assert not check.ok and "max_rows" in check.detail


# --- بقیه‌ی بررسی‌ها ---------------------------------------------------------

def test_red_while_a_todo_is_left_in_the_knowledge(make, tmp_path):
    name = make(files={"documentation.md": f"# x\n\n{customer.TODO_MARKER}: fill me\n"})
    check = results(name, tmp_path)["دانش دامنه کامل است"]
    assert not check.ok and "documentation.md" in check.detail


def test_red_when_an_example_is_rejected_by_the_guard(make, tmp_path):
    bad = "- question: q\n  source: inverter_data\n  why: w\n  query:\n    - $out: stolen\n"
    name = make(files={"examples.yaml": bad})
    check = results(name, tmp_path)["همه‌ی نمونه‌ها از گارد رد می‌شوند"]
    assert not check.ok and "نمونه‌ی 1" in check.detail


def test_red_with_fewer_than_ten_golden_questions(make, tmp_path):
    few = "- question: q\n  expect: {value: 1}\n" * 3
    name = make(files={"golden_questions.yaml": few})
    assert not results(name, tmp_path)["دست‌کم 10 سوال طلایی"].ok


def test_the_checks_use_the_named_customers_sources_not_the_active_ones(make, tmp_path):
    """مشتری فعال demo است؛ بررسی باید با فهرست سفید *همان پوشه* بسنجد."""
    name = make(profile={"  - inverter_data\n": ""}, files={
        "examples.yaml": "- question: q\n  source: inverter_data\n  why: w\n  query: [{$match: {}}]\n"})
    check = results(name, tmp_path)["همه‌ی نمونه‌ها از گارد رد می‌شوند"]
    assert not check.ok and "مجاز نیست" in check.detail


def test_a_broken_profile_stops_the_rest_with_a_clear_line(make, tmp_path):
    name = make(profile={"max_rows": "max_row"})
    checks = readiness.run_checks(name, tmp_path)
    assert len(checks) == 2 and not checks[0].ok and "max_rows" in checks[0].detail


def test_an_unreachable_server_does_not_leak_its_message(make, tmp_path, monkeypatch):
    name = make()
    monkeypatch.setenv(f"RASAM_{VARIABLE}", "mongodb://secret-user:secret-pass@127.0.0.1:1/x")
    text = readiness.render(readiness.run_checks(name, tmp_path))
    assert "secret-pass" not in text and "اتصال ناموفق" in text


# --- فرمان `check` -----------------------------------------------------------

def test_the_command_exits_zero_only_when_everything_is_green(make, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CUSTOMERS_DIR", tmp_path)
    lines: list[str] = []
    assert onboard.run_check(make(), say=lines.append) == 0
    assert "آماده‌ی تحویل است" in "\n".join(lines)

    lines.clear()
    broken = make(profile={"  max_rows: 1000\n": ""})
    assert onboard.run_check(broken, say=lines.append) == 1
    assert "❌" in "\n".join(lines)
