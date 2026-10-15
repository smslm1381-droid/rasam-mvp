"""تست گارد SQL — بدون مدل. بیشترشان بدون دیتابیس؛ آزمون «اجرا می‌شود» روی MySQL محلی.

دروازه‌ی امنیتی به همان سخت‌گیری گارد مونگوست و به همان شکل تست می‌شود: هر
حمله‌ی مدل تهدید یک تست دارد، و مهم‌ترین‌ها: کوئری ردشده هرگز نتیجه‌ی `query` ندارد،
چیزی که اجرا می‌شود SQLِ بازتولیدشده از درخت است، و `OR 1=1` از شرط سطری فرار نمی‌کند.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pymysql
import pytest
import sqlglot
import yaml

from rasam import config
from rasam.databases.mysql import connection, guard

SOURCE = "inverter_data"
ALLOWED = {SOURCE, "string_data"}


def run(sql, source=SOURCE, **kwargs):
    return guard.check(sql, source, ALLOWED, **kwargs)


@pytest.fixture(autouse=True)
def cap(monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, max_rows=1000))


# --- سالم‌ها ------------------------------------------------------------------

def test_a_plain_aggregate_is_accepted_and_gets_the_row_cap():
    result = run("SELECT AVG(int_temp) FROM inverter_data")
    assert result.ok and result.query == "SELECT AVG(int_temp) FROM inverter_data LIMIT 1000"
    assert result.max_time_ms == config.settings.query_timeout_ms


def test_a_full_query_with_filter_group_having_order_is_accepted():
    sql = ("SELECT work_state, COUNT(*) AS c FROM inverter_data WHERE int_temp > 10 "
           "AND work_state IN ('Run', 'Standby') GROUP BY work_state HAVING COUNT(*) > 1 "
           "ORDER BY c DESC LIMIT 5")
    assert run(sql).ok


def test_the_unsigned_reactive_power_trap_expression_is_accepted():
    sql = ("SELECT AVG(CASE WHEN tot_reactive_pow >= 2147483648 THEN tot_reactive_pow - 4294967296 "
           "ELSE tot_reactive_pow END) AS v FROM inverter_data")
    assert run(sql).ok


# --- حمله‌ها: هرکدام رد، و هیچ کوئری‌ای برجا نمی‌ماند ------------------------

@pytest.mark.parametrize("sql", [
    "SELECT 1 FROM inverter_data; DROP TABLE inverter_data",
    "SELECT 1 FROM inverter_data; SELECT 2 FROM inverter_data",
    "SELECT COUNT(*) FROM inverter_data WHERE SLEEP(10) = 0",
    "SELECT BENCHMARK(100000000, MD5('x')) FROM inverter_data",
    "SELECT LOAD_FILE('/etc/passwd') FROM inverter_data",
    "SELECT ROUND(AVG(IF(int_temp > 0, SLEEP(1), 1)), 2) FROM inverter_data",
    "SELECT * FROM inverter_data INTO OUTFILE '/tmp/x'",
    "SELECT int_temp INTO @stolen FROM inverter_data",
    "SELECT @@version FROM inverter_data",
    "SELECT /*+ SET_VAR(sql_select_limit=1) */ int_temp FROM inverter_data",
    "SELECT int_temp FROM inverter_data FOR UPDATE",
    "SELECT int_temp FROM inverter_data LOCK IN SHARE MODE",
    "DELETE FROM inverter_data",
    "UPDATE inverter_data SET int_temp = 0",
    "INSERT INTO inverter_data (int_temp) VALUES (1)",
    "DROP TABLE inverter_data",
    "SELECT * FROM billing",
    "SELECT * FROM information_schema.tables",
    "SELECT user FROM mysql.user",
    "SELECT * FROM solar_telemetry.inverter_data",
    "SELECT a.int_temp FROM inverter_data a JOIN string_data b ON 1 = 1",
    "SELECT int_temp FROM inverter_data UNION SELECT voltage FROM string_data",
    "SELECT int_temp FROM inverter_data WHERE int_temp IN (SELECT voltage FROM string_data)",
    "WITH c AS (SELECT 1) SELECT * FROM c",
    "SELECT SUM(int_temp) OVER (PARTITION BY work_state) FROM inverter_data",
])
def test_every_attack_is_rejected_and_leaves_no_query(sql):
    result = run(sql)
    assert result.ok is False and result.query is None and result.reason


def test_a_table_other_than_the_declared_source_is_rejected():
    """مدل `table` را `inverter_data` اعلام کرد ولی SQL از جدول دیگر می‌خواند."""
    result = run("SELECT voltage FROM string_data", source=SOURCE)
    assert not result.ok and "یکی نیست" in result.reason


def test_the_forbidden_function_is_named_with_its_reason():
    assert "SLEEP" in run("SELECT SLEEP(5) FROM inverter_data").reason


def test_an_unknown_function_is_rejected_as_not_whitelisted():
    result = run("SELECT MADE_UP_FUNCTION(int_temp) FROM inverter_data")
    assert not result.ok and "MADE_UP_FUNCTION" in result.reason


# --- چیزی که اجرا می‌شود SQLِ بازتولیدشده است --------------------------------

def test_an_executable_comment_does_not_survive_into_the_executed_sql():
    """MySQL محتوای `/*! … */` را اجرا می‌کند؛ در SQLِ بازتولیدشده کامنتی نیست."""
    result = run("SELECT /*!50000 int_temp */ FROM inverter_data /* x */ -- y")
    final = result.query or ""
    assert "/*" not in final and "--" not in final and "#" not in final


def test_the_executed_sql_is_reparsed_to_the_same_whitelist():
    result = run("SELECT AVG(int_temp) FROM inverter_data")
    tree = sqlglot.parse_one(result.query, dialect="mysql")
    assert guard._scan(tree) is None


# --- سقف رکورد و شرط سطری -----------------------------------------------------

def test_a_missing_limit_is_added():
    assert run("SELECT int_temp FROM inverter_data").query.endswith("LIMIT 1000")


def test_a_limit_above_the_cap_is_lowered():
    assert run("SELECT int_temp FROM inverter_data LIMIT 1000000000").query.endswith("LIMIT 1000")


def test_a_limit_below_the_cap_is_kept():
    assert run("SELECT int_temp FROM inverter_data LIMIT 7").query.endswith("LIMIT 7")


def test_without_a_cap_nothing_is_added(monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, max_rows=None))
    assert "LIMIT" not in run("SELECT int_temp FROM inverter_data").query


def test_the_row_filter_is_anded_outside_the_models_own_where():
    """مهم‌ترین تست: `OR 1=1` مدل داخل پرانتز می‌ماند و نمی‌تواند از شرط سطری فرار کند."""
    result = run("SELECT int_temp FROM inverter_data WHERE int_temp > 1 OR 1 = 1",
                 row_filter={"plant_id": 3})
    assert result.query == ("SELECT int_temp FROM inverter_data WHERE plant_id = 3 "
                            "AND (int_temp > 1 OR 1 = 1) LIMIT 1000")


def test_a_row_filter_is_added_even_when_the_model_wrote_no_where():
    result = run("SELECT int_temp FROM inverter_data", row_filter={"work_state": "Run"})
    assert "WHERE work_state = 'Run'" in result.query


@pytest.mark.parametrize("bad", [{"a b": 1}, {"x; DROP": 1}, {"a": [1]}, {1: 2}, {"a": object()}])
def test_a_malformed_row_filter_is_rejected_not_executed(bad):
    assert run("SELECT int_temp FROM inverter_data", row_filter=bad).ok is False


# --- هرگز استثنا --------------------------------------------------------------

@pytest.mark.parametrize("query", [None, 0, "", "   ", [], {}, ["SELECT 1"], "x" * 50_000,
                                   "(" * 5000, "SELECT " + "(" * 3000 + "1" + ")" * 3000,
                                   "\x00", "SELECT '", "SELECT `", "SELECT /*", "';--"])
def test_garbage_queries_are_rejected_never_raise(query):
    result = run(query)
    assert result.ok is False and result.query is None


@pytest.mark.parametrize("source", [None, "", 0, ["inverter_data"], {"a": 1}, b"x", "no_such_table"])
def test_garbage_sources_are_rejected_never_raise(source):
    assert run("SELECT 1 FROM inverter_data", source=source).ok is False


# --- فهرست تابع‌هایی که به مدل می‌گوییم، با گارد یکی است ---------------------

SAMPLES = {
    "COUNT": "COUNT(int_temp)", "SUM": "SUM(int_temp)", "AVG": "AVG(int_temp)", "MIN": "MIN(int_temp)",
    "MAX": "MAX(int_temp)", "STDDEV": "STDDEV(int_temp)", "STDDEV_POP": "STDDEV_POP(int_temp)",
    "STDDEV_SAMP": "STDDEV_SAMP(int_temp)", "VARIANCE": "VARIANCE(int_temp)",
    "VAR_SAMP": "VAR_SAMP(int_temp)", "ABS": "ABS(int_temp)",
    "ROUND": "ROUND(int_temp, 1)", "FLOOR": "FLOOR(int_temp)", "CEIL": "CEIL(int_temp)",
    "CEILING": "CEILING(int_temp)", "SQRT": "SQRT(ABS(int_temp))", "POW": "POW(int_temp, 2)",
    "POWER": "POWER(int_temp, 2)", "EXP": "EXP(LEAST(int_temp, 5))", "LN": "LN(ABS(int_temp) + 1)",
    "LOG": "LOG(ABS(int_temp) + 1)", "LOG10": "LOG10(ABS(int_temp) + 1)", "MOD": "MOD(ts, 7)",
    "SIGN": "SIGN(int_temp)", "GREATEST": "GREATEST(int_temp, 0)", "LEAST": "LEAST(int_temp, 100)",
    "IF": "IF(int_temp > 20, 1, 0)", "IFNULL": "IFNULL(int_temp, 0)", "COALESCE": "COALESCE(int_temp, 0)",
    "NULLIF": "NULLIF(int_temp, 0)", "CAST": "CAST(int_temp AS DECIMAL(10, 2))",
    "CONVERT": "CONVERT(int_temp, SIGNED)", "YEAR": "YEAR(FROM_UNIXTIME(ts))",
    "MONTH": "MONTH(FROM_UNIXTIME(ts))", "DAY": "DAY(FROM_UNIXTIME(ts))", "HOUR": "HOUR(FROM_UNIXTIME(ts))",
    "MINUTE": "MINUTE(FROM_UNIXTIME(ts))", "SECOND": "SECOND(FROM_UNIXTIME(ts))",
    "DATE": "DATE(FROM_UNIXTIME(ts))", "EXTRACT": "EXTRACT(HOUR FROM FROM_UNIXTIME(ts))",
    "DATE_FORMAT": "DATE_FORMAT(FROM_UNIXTIME(ts), '%Y-%m-%d')", "FROM_UNIXTIME": "FROM_UNIXTIME(ts)",
    "DATE_ADD": "DATE_ADD(FROM_UNIXTIME(ts), INTERVAL 1 DAY)", "DATE_SUB": "DATE_SUB(FROM_UNIXTIME(ts), INTERVAL 1 DAY)",
    "DATEDIFF": "DATEDIFF(FROM_UNIXTIME(ts), FROM_UNIXTIME(0))",
    "TIMESTAMPDIFF": "TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(0), FROM_UNIXTIME(ts))", "CURDATE": "CURDATE()",
    "CONCAT": "CONCAT(work_state, 'x')", "LOWER": "LOWER(work_state)", "UPPER": "UPPER(work_state)",
    "SUBSTRING": "SUBSTRING(work_state, 1, 2)", "LENGTH": "LENGTH(work_state)", "TRIM": "TRIM(work_state)",
    "UNIX_TIMESTAMP": "UNIX_TIMESTAMP(FROM_UNIXTIME(ts))", "NOW": "NOW()",
}


def test_every_function_the_model_is_told_about_has_a_sample():
    assert set(SAMPLES) == set(guard.FUNCTIONS_DISPLAY)


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_every_advertised_function_is_accepted_by_the_guard(name):
    """پرامپت از `FUNCTIONS` نقل می‌کند؛ تابعی که به مدل مجاز می‌گوییم باید واقعاً مجاز باشد."""
    result = run(f"SELECT {SAMPLES[name]} AS v FROM inverter_data")
    assert result.ok, result.reason


def test_every_advertised_function_actually_runs_on_mysql():
    """بازتولید sqlglot باید MySQLِ معتبر باشد، نه فقط از گارد بگذرد."""
    uri = config.env_value("MYSQL_URI")
    if not uri:
        pytest.skip("RASAM_MYSQL_URI در `.env` نیست.")
    try:
        conn = connection.connect(uri)
    except pymysql.MySQLError:
        pytest.skip("MySQL محلی در دسترس نیست.")
    failures = []
    with conn, conn.cursor() as cursor:
        for name, call in sorted(SAMPLES.items()):
            checked = run(f"SELECT {call} AS v FROM inverter_data LIMIT 3")
            try:
                cursor.execute(checked.query)
                cursor.fetchall()
            except pymysql.MySQLError as error:
                failures.append(f"{name}: {error.args[0]} در «{checked.query}»")
    assert not failures, "\n".join(failures)


# --- نمونه‌های حمله‌ی خودِ آداپتور (attacks.yaml) ----------------------------

def _attack_file() -> dict:
    path = Path(guard.__file__).with_name("attacks.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _resolve(text: str) -> str:
    return (text.replace("@allowed", SOURCE).replace("@forbidden", "billing")
            .replace("@filter_field", "work_state").replace("@filter_value", "Run"))


def test_every_rejected_attack_in_the_catalogue_is_rejected():
    categories = _attack_file()["categories"]
    for name in ("write", "code_execution", "unauthorized_source", "multi_statement"):
        for attack in categories[name]["attacks"]:
            result = run(_resolve(attack["query"]), source=_resolve(attack["source"]))
            assert not result.ok, f"{name}: «{attack['description']}» قبول شد"


def test_every_safe_query_in_the_catalogue_is_accepted():
    for item in _attack_file()["safe"]:
        result = run(_resolve(item["query"]), source=_resolve(item["source"]))
        assert result.ok, f"«{item['description']}» رد شد: {result.reason}"
