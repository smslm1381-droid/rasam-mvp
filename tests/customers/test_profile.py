"""تست پروفایل مشتری و ساخت گراف بر اساس قابلیت‌ها."""

from __future__ import annotations

from pathlib import Path

import pytest

from rasam import config, customer
from rasam.core import graph

ROOT = config.CUSTOMERS_DIR
# پروفایل‌هایی که فقط برای تست‌اند، کنار مشتری‌های واقعی نمی‌نشینند.
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "customers"


def test_demo_profile_contains_configuration_without_a_secret():
    profile = customer.load_profile("demo", ROOT)
    assert profile.db_type == "mongodb"
    assert profile.connection_env == "MONGO_URI"
    assert "inverter_data" in profile.allowed_sources
    assert "chart" in profile.capabilities
    assert profile.limits["max_rows"] == 1000


def test_profiles_build_different_graphs():
    chart_graph = graph.build_graph(customer.load_profile("demo", ROOT).capabilities)
    plain_graph = graph.build_graph(customer.load_profile("no_chart", FIXTURES).capabilities)
    assert "chart" in chart_graph.nodes
    assert "chart" not in plain_graph.nodes


def test_missing_profile_is_rejected(tmp_path):
    with pytest.raises(customer.ProfileError, match="پیدا نشد"):
        customer.load_profile("missing", tmp_path)


# --- پروفایل سخت‌گیر (قدم ۱۸) ------------------------------------------------

BASE = """\
db_type: mongodb
connection_env: MONGO_URI
database: solar_telemetry
allowed_sources: [inverter_data]
capabilities: [summary, repair]
limits: {max_rows: 1000}
"""


def write_profile(tmp_path, text: str = BASE) -> Path:
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "profile.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def broken(tmp_path, old: str, new: str) -> str:
    """پیام خطای پروفایلی که فقط یک خطش را از BASE عوض کرده‌ایم."""
    with pytest.raises(customer.ProfileError) as error:
        customer.load_profile("t", write_profile(tmp_path, BASE.replace(old, new)))
    return str(error.value)


def test_the_valid_base_profile_loads(tmp_path):
    profile = customer.load_profile("t", write_profile(tmp_path))
    assert profile.capabilities == {"summary", "repair"}


def test_a_misspelled_limit_is_an_error_not_silently_ignored(tmp_path):
    """مهم‌ترین تست: `max_row` قبلاً بی‌صدا نادیده گرفته می‌شد و سقف رکورد خاموش می‌ماند."""
    message = broken(tmp_path, "max_rows", "max_row")
    assert "max_row" in message and "max_rows" in message  # حدس «منظورتان این بود؟»


def test_an_unknown_top_level_field_is_an_error(tmp_path):
    message = broken(tmp_path, "capabilities:", "capabilites:")
    assert "capabilites" in message and "شناخته‌شده نیست" in message


@pytest.mark.parametrize("secret", [
    "mongodb://rasam_ro:hunter2@localhost/db",
    "mongodb+srv://u:p@cluster.example.net/db",
    "postgresql://u:p@host/db",
    "postgres://u:p@host/db",
    "password=hunter2",
])
def test_a_connection_string_or_password_in_the_profile_is_refused(tmp_path, secret):
    message = broken(tmp_path, "connection_env: MONGO_URI", f"connection_env: '{secret}'")
    assert "رمز" in message
    # خودِ مقدار نباید به ترمینال و لاگ برسد.
    assert "hunter2" not in message and "rasam_ro" not in message


def test_a_secret_hiding_in_an_unknown_field_gets_the_secret_message(tmp_path):
    message = broken(tmp_path, "limits:", "uri: mongodb://u:p@h/d\nlimits:")
    assert "رمز" in message


def test_connection_env_must_be_a_variable_name_not_a_value(tmp_path):
    assert "نام" in broken(tmp_path, "MONGO_URI", "my secret value")


def test_an_unknown_capability_is_an_error_with_the_allowed_list(tmp_path):
    message = broken(tmp_path, "[summary, repair]", "[summary, chrat]")
    assert "chrat" in message and "chart" in message


@pytest.mark.parametrize("step", ["prepare", "generate", "validate", "execute"])
def test_the_core_cannot_be_switched_off_as_a_capability(tmp_path, step):
    """گارد هرگز یک گزینه نیست."""
    message = broken(tmp_path, "[summary, repair]", f"[summary, {step}]")
    assert "هسته" in message and "گارد" in message


def test_the_guard_cannot_be_switched_off_as_a_field_either(tmp_path):
    assert "هسته" in broken(tmp_path, "limits:", "validate: false\nlimits:")


def test_an_unknown_db_type_fails_at_startup_not_at_the_first_question():
    from rasam.databases import registry

    profile = customer.load_profile("demo", ROOT)
    registry.check_db_type(profile)  # شناخته‌شده: بی‌صدا
    unknown = customer.CustomerProfile(**{**profile.__dict__, "db_type": "oracle"})
    with pytest.raises(config.ConfigError, match="oracle"):
        registry.check_db_type(unknown)


# --- گراف بر اساس قابلیت‌ها --------------------------------------------------

def nodes(*capabilities: str) -> set[str]:
    return set(graph.build_graph(frozenset(capabilities)).nodes) - {"__start__"}


def test_the_core_is_always_in_the_graph():
    assert nodes() == {"prepare", "generate", "validate", "execute"}


def test_each_optional_node_exists_only_when_its_capability_is_listed():
    assert "summarize" in nodes("summary") and "summarize" not in nodes("repair")
    assert "repair" in nodes("repair") and "repair" not in nodes("summary")
    assert "chart" in nodes("chart") and "chart" not in nodes("summary")


def test_export_capabilities_do_not_add_nodes():
    """خروجی فایل مال لایه‌ی نمایش است، نه گراف."""
    assert nodes("export_csv", "export_excel") == nodes()


def test_demo_has_every_optional_node():
    demo = customer.load_profile("demo", ROOT).capabilities
    assert graph.graph_nodes(demo) == [
        "prepare", "generate", "validate", "execute", "summarize", "chart", "repair"]


def test_the_database_name_belongs_to_the_profile_and_is_required(tmp_path):
    """نام دیتابیس دیگر در `.env` نیست: پروفایل بدون آن معتبر نیست."""
    message = broken(tmp_path, "database: solar_telemetry\n", "")
    assert "database" in message


def test_the_profile_carries_the_database_name():
    assert customer.load_profile("demo", ROOT).database == "solar_telemetry"
