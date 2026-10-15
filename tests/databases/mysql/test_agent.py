"""تست ایجنت MySQL روی MySQL محلی: اجرا، لایه‌ی دوم فقط-خواندنی، و بررسی دسترسی."""

from __future__ import annotations

import datetime
import decimal
import time

import pymysql
import pytest

from rasam import config
from rasam.databases.base import Result
from rasam.databases.mysql import MySQLAgent, connection
from rasam.databases.mysql.agent import _plain
from tests.secret import Secret

ALLOWED = frozenset({"inverter_data"})


@pytest.fixture(scope="module")
def uri() -> str:
    value = config.env_value("MYSQL_URI")
    if not value:
        pytest.skip("RASAM_MYSQL_URI در `.env` نیست.")
    return Secret(value)


@pytest.fixture(scope="module")
def admin_uri() -> str:
    value = config.env_value("MYSQL_ADMIN_URI")
    if not value:
        pytest.skip("RASAM_MYSQL_ADMIN_URI در `.env` نیست.")
    return Secret(value)


@pytest.fixture(scope="module")
def agent(uri) -> MySQLAgent:
    candidate = MySQLAgent(uri, "solar_telemetry", ALLOWED)
    try:
        candidate.list_sources()
    except pymysql.MySQLError:
        pytest.skip("MySQL محلی در دسترس نیست.")
    return candidate


def accepted(sql: str, max_time_ms: int = 60_000) -> Result:
    return Result(ok=True, query=sql, reason="", max_time_ms=max_time_ms)


# --- ساده‌سازی نوع‌ها ---------------------------------------------------------

def test_mysql_only_types_leave_the_agent_as_plain_values():
    """`Decimal` به JSON و Excel نمی‌رود؛ ترجمه داخل ایجنت است (درس تصمیم ۵۵)."""
    assert _plain(decimal.Decimal("12.5")) == 12.5
    assert _plain(datetime.datetime(2025, 1, 1)) == datetime.datetime(2025, 1, 1)
    assert _plain(datetime.timedelta(hours=1)) == "1:00:00"
    assert _plain(b"abc") == "abc"
    assert _plain(None) is None and _plain(3) == 3 and _plain("x") == "x"


# --- اجرا ---------------------------------------------------------------------

def test_the_same_average_as_mongo_comes_through_the_whole_path(agent):
    checked = agent.validate_query("inverter_data", "SELECT AVG(int_temp) AS avg_temp FROM inverter_data")
    rows = agent.execute("inverter_data", checked)
    assert rows[0]["avg_temp"] == pytest.approx(28.6077, abs=1e-3)


def test_execute_refuses_a_query_the_guard_did_not_accept(agent):
    with pytest.raises(ValueError, match="پذیرفته"):
        agent.execute("inverter_data", Result(ok=False, query=None, reason="رد شد"))


def test_a_declared_cap_limits_the_rows_for_real(agent, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(config, "settings", replace(config.settings, max_rows=5))
    checked = agent.validate_query("inverter_data", "SELECT int_temp FROM inverter_data")
    assert len(agent.execute("inverter_data", checked)) == 5


# --- لایه‌ی دوم: تراکنش فقط-خواندنی، جدا از دسترسی‌های کاربر ------------------

def test_the_transaction_itself_is_read_only_even_for_a_user_who_could_write(admin_uri):
    """کاربر مدیر اجازه‌ی نوشتن دارد؛ ولی اتصال آداپتور در تراکنش READ ONLY است.

    این لایه‌ی دوم قاعده‌ی ۲ است: اگر مشتری اشتباهاً به کاربر برنامه دسترسی نوشتن بدهد،
    هنوز چیزی نوشته نمی‌شود. گارد را عمداً دور می‌زنیم (`Result` دستی) تا فقط همین لایه سنجیده شود.
    """
    with connection.connect(admin_uri, "solar_telemetry") as owner, owner.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS `zz_readonly_probe`")
        cursor.execute("CREATE TABLE `zz_readonly_probe` (`n` INT)")
        cursor.execute("INSERT INTO `zz_readonly_probe` VALUES (1)")
        try:
            powerful = MySQLAgent(admin_uri, "solar_telemetry", frozenset({"zz_readonly_probe"}))
            with pytest.raises(pymysql.MySQLError) as error:
                powerful.execute("zz_readonly_probe", accepted("DELETE FROM `zz_readonly_probe`"))
            assert error.value.args[0] == 1792  # ER_CANT_EXECUTE_IN_READ_ONLY_TRANSACTION
            cursor.execute("SELECT COUNT(*) AS n FROM `zz_readonly_probe`")
            assert cursor.fetchone()["n"] == 1
        finally:
            cursor.execute("DROP TABLE IF EXISTS `zz_readonly_probe`")


def test_a_slow_query_is_cut_by_the_guards_time_limit(admin_uri):
    """سقف زمان از نتیجه‌ی گارد می‌آید (تصمیم ۲۳)، نه از تنظیم اتصال."""
    heavy = "SELECT SUM(a.`int_temp` * b.`int_temp`) FROM `inverter_data` a CROSS JOIN `inverter_data` b"
    slow = MySQLAgent(admin_uri, "solar_telemetry", ALLOWED)
    started = time.perf_counter()
    with pytest.raises(pymysql.MySQLError) as error:
        slow.execute("inverter_data", accepted(heavy, max_time_ms=300))
    assert error.value.args[0] == 3024  # ER_QUERY_TIMEOUT
    assert time.perf_counter() - started < 5


# --- بررسی دسترسی -------------------------------------------------------------

def test_the_application_user_is_read_only(agent):
    report = agent.check_read_only()
    assert report.read_only and "SELECT" in report.detail


def test_the_admin_user_is_not_read_only_and_the_privileges_are_named(admin_uri):
    report = MySQLAgent(admin_uri, "solar_telemetry").check_read_only()
    assert not report.read_only and "دسترسی غیرخواندنی" in report.detail
    assert "mysql://" not in report.detail


def test_a_user_with_one_extra_write_privilege_is_caught(admin_uri):
    """نه فقط «ادمین»: یک `INSERT` اضافه روی یک جدول هم باید قرمز شود."""
    with connection.connect(admin_uri, "solar_telemetry") as owner, owner.cursor() as cursor:
        cursor.execute("DROP USER IF EXISTS 'zz_sneaky'@'%'")
        cursor.execute("CREATE USER 'zz_sneaky'@'%' IDENTIFIED BY 'zz-sneaky-pass-1'")
        cursor.execute("GRANT SELECT ON `solar_telemetry`.`inverter_data` TO 'zz_sneaky'@'%'")
        cursor.execute("GRANT INSERT ON `solar_telemetry`.`inverter_data` TO 'zz_sneaky'@'%'")
        try:
            sneaky = MySQLAgent("mysql://zz_sneaky:zz-sneaky-pass-1@127.0.0.1:3306/solar_telemetry",
                                "solar_telemetry", ALLOWED)
            report = sneaky.check_read_only()
            assert not report.read_only and "INSERT" in report.detail
        finally:
            cursor.execute("DROP USER IF EXISTS 'zz_sneaky'@'%'")


def test_a_user_holding_grant_option_is_not_read_only(admin_uri):
    with connection.connect(admin_uri, "solar_telemetry") as owner, owner.cursor() as cursor:
        cursor.execute("DROP USER IF EXISTS 'zz_granter'@'%'")
        cursor.execute("CREATE USER 'zz_granter'@'%' IDENTIFIED BY 'zz-granter-pass-1'")
        cursor.execute("GRANT SELECT ON `solar_telemetry`.`inverter_data` TO 'zz_granter'@'%' WITH GRANT OPTION")
        try:
            report = MySQLAgent("mysql://zz_granter:zz-granter-pass-1@127.0.0.1:3306/solar_telemetry",
                                "solar_telemetry", ALLOWED).check_read_only()
            assert not report.read_only and "GRANT OPTION" in report.detail
        finally:
            cursor.execute("DROP USER IF EXISTS 'zz_granter'@'%'")


# --- فهرست‌ها برای ابزار تحویل ------------------------------------------------

def test_list_sources_and_fields_work_without_the_active_customer(agent):
    assert "inverter_data" in agent.list_sources()
    assert "int_temp" in agent.list_fields("inverter_data")


def test_describe_schema_with_an_explicit_connection_is_limited_to_the_whitelist(agent):
    text = agent.describe_schema()
    assert "Table: inverter_data" in text and "string_data" not in text
