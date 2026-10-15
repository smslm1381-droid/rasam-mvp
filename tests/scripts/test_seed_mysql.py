"""تست seed دیتابیس دوم: همان داده، همان ردیف‌ها، و کاربر واقعاً فقط-خواندنی.

این تست‌ها اتصال برنامه (`rasam_ro`) و اتصال مدیر را از `.env` می‌خوانند و اگر
MySQL محلی بالا نیست با پیام روشن skip می‌شوند. هدفشان قدم ۲۱ است: اگر جواب دو
دیتابیس بعداً فرق کرد، تقصیر آداپتور باشد نه داده (تصمیم ۶۵).
"""

from __future__ import annotations

import pymysql
import pytest

from rasam import config
from rasam.databases.mongodb import schema as mongo_schema
from rasam.databases.mysql import connection
from scripts import csv_loader
from tests.secret import Secret

CSV_FILES = sorted(config.settings.csv_dir.glob("*.csv")) if config.settings.csv_dir else []
TABLES = ["inverter_data", "lvpanel_data", "mvpanel_data", "string_data"]


@pytest.fixture(scope="module")
def uri() -> str:
    value = config.env_value("MYSQL_URI")
    if not value:
        pytest.skip("RASAM_MYSQL_URI در `.env` نیست.")
    return Secret(value)


@pytest.fixture(scope="module")
def mysql(uri):
    """اتصال با همان کاربر فقط-خواندنیِ برنامه — نه با کاربر مدیر."""
    try:
        conn = connection.connect(uri)
    except pymysql.MySQLError as error:
        pytest.skip(f"MySQL محلی در دسترس نیست (کد {error.args[0] if error.args else '؟'}).")
    yield conn
    conn.close()


def scalar(conn, sql: str):
    with conn.cursor() as cursor:
        cursor.execute(sql)
        return next(iter(cursor.fetchone().values()))


@pytest.mark.parametrize("csv_path", CSV_FILES, ids=lambda p: csv_loader.table_name(p))
def test_row_count_matches_the_csv(mysql, csv_path):
    expected = len(csv_loader.read_frame(csv_path))
    assert scalar(mysql, f"SELECT COUNT(*) FROM `{csv_loader.table_name(csv_path)}`") == expected


@pytest.mark.parametrize("table", TABLES)
def test_columns_are_the_same_fields_mongo_has(mysql, table):
    """همان فیلدها، تا دانش دامنه‌ی دمو برای هر دو معتبر بماند."""
    try:
        mongo_fields = set(mongo_schema.field_names(mongo_schema.connect(), table))
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"مونگوی محلی در دسترس نیست: {type(error).__name__}")
    with mysql.cursor() as cursor:
        cursor.execute(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s", (table,))
        assert {row["name"] for row in cursor.fetchall()} == mongo_fields


def test_an_average_is_the_same_number_in_both_databases(mysql):
    mongo = next(mongo_schema.connect()["inverter_data"].aggregate(
        [{"$group": {"_id": None, "v": {"$avg": "$int_temp"}}}]))["v"]
    assert scalar(mysql, "SELECT AVG(`int_temp`) FROM `inverter_data`") == pytest.approx(mongo)


def test_the_unsigned_reactive_power_trap_is_kept_raw(mysql):
    """مثل مونگو: خام ذخیره می‌شود، تا تله و دانشش در هر دو یکی باشد."""
    big = scalar(mysql, "SELECT COUNT(*) FROM `inverter_data` WHERE `tot_reactive_pow` >= 2147483648")
    assert big == 5927  # عددی که در بخش ۹ اندازه‌گیری شده


def test_an_empty_cell_is_null_not_nan(mysql):
    """`NaN` در MySQL پذیرفته نمی‌شود؛ نبود مقدار باید `NULL` بماند."""
    nulls = scalar(mysql, "SELECT COUNT(*) FROM `inverter_data` WHERE `int_temp` IS NULL")
    assert nulls == len(csv_loader.read_frame(next(p for p in CSV_FILES if "inverter" in p.name))
                        ["int_temp"].loc[lambda s: s.isna()])


def test_the_all_empty_column_was_not_created(mysql):
    with mysql.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM information_schema.columns "
                       "WHERE table_schema = DATABASE() AND column_name = 'fa_al_message'")
        assert cursor.fetchone()["n"] == 0


# --- فقط-خواندنی بودن، روی دیتابیس واقعی -------------------------------------

@pytest.mark.parametrize("statement", [
    "INSERT INTO `inverter_data` (`int_temp`) VALUES (1)",
    "UPDATE `inverter_data` SET `int_temp` = 0",
    "DELETE FROM `inverter_data`",
    "DROP TABLE `inverter_data`",
    "CREATE TABLE `evil` (`a` INT)",
])
def test_the_application_user_cannot_write(mysql, statement):
    """دسترسی ردشده: ۱۱۴۲ (جدول) یا ۱۰۴۴/۱۲۲۷ (دیتابیس). نباید هیچ‌کدام اجرا شود."""
    with pytest.raises(pymysql.MySQLError) as error:
        with mysql.cursor() as cursor:
            cursor.execute(statement)
    assert error.value.args[0] in (1142, 1044, 1227, 1370)


def test_the_user_sees_only_the_four_granted_tables(mysql, uri):
    admin = config.env_value("MYSQL_ADMIN_URI")
    if not admin:
        pytest.skip("RASAM_MYSQL_ADMIN_URI در `.env` نیست.")
    with connection.connect(admin, database=connection.parse_uri(uri)["database"]) as owner:
        with owner.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS `zz_hidden_users` (`secret` VARCHAR(10))")
        try:
            with mysql.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                visible = {next(iter(row.values())) for row in cursor.fetchall()}
                assert visible == set(TABLES)
                with pytest.raises(pymysql.MySQLError):
                    cursor.execute("SELECT * FROM `zz_hidden_users`")
        finally:
            with owner.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS `zz_hidden_users`")
