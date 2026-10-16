"""تست مشتری `demo-mysql`: همان نیروگاه، همان داده، روی MySQL — فقط با فایل.

بدون سهمیه‌ی مدل، سه چیز سنجیده می‌شود:

۱. **سقف کیفیت:** برای هر ۱۵ سوال طلایی، SQLِ درست را دست می‌نویسیم و از مسیر واقعی
   گارد ← MySQL اجرا می‌کنیم. اگر سوالی در اینجا غلط درآید، حتی یک مدل بی‌نقص هم
   نمی‌تواند درستش کند — یعنی اشکال از آداپتور یا دانش است، نه مدل (تصمیم ۶۵).
۲. **مسیر کامل:** گراف واقعی با مدل جعلیِ اسکریپت‌شده، روی MySQL واقعی، در یک
   پروسه‌ی جدا با `RASAM_CUSTOMER=demo-mysql` (هر مشتری یک پروسه، تصمیم ۸۰).
۳. **هم‌ارزی فایل‌ها:** سوالات طلایی دو مشتری عیناً یکی‌اند.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pymysql
import pytest
import yaml

from rasam import config
from rasam.core.answer import Answer
from rasam.databases.mysql import MySQLAgent
from scripts.evaluate import grade
from tests.secret import Secret

ROOT = Path(__file__).resolve().parents[2]
DEMO = config.CUSTOMERS_DIR / "demo"
DEMO_MYSQL = config.CUSTOMERS_DIR / "demo-mysql"

TABLES = frozenset({"inverter_data", "lvpanel_data", "mvpanel_data", "string_data"})
UNSIGNED = ("CASE WHEN tot_reactive_pow >= 2147483648 THEN tot_reactive_pow - 4294967296 "
            "ELSE tot_reactive_pow END")

# SQLِ درست برای هر سوال طلایی، به همان ترتیب فایل. `None` یعنی داده‌اش در دیتابیس نیست.
GOLDEN_SQL: dict[str, tuple[str, str] | None] = {
    "میانگین دمای داخلی اینورترها چقدر است؟": ("inverter_data", "SELECT AVG(int_temp) FROM inverter_data"),
    "بیشترین دمای داخلی اینورتر چقدر بوده؟": ("inverter_data", "SELECT MAX(int_temp) FROM inverter_data"),
    "میانگین ولتاژ متوسط پنل فشار ضعیف چقدر است؟": ("lvpanel_data", "SELECT AVG(voltage_avg) FROM lvpanel_data"),
    "بیشترین توان استرینگ‌ها چقدر بوده؟": ("string_data", "SELECT MAX(power) FROM string_data"),
    "چند رکورد در پنل فشار متوسط ثبت شده است؟": ("mvpanel_data", "SELECT COUNT(*) FROM mvpanel_data"),
    "میانگین توان راکتیو اینورتر چقدر است؟": ("inverter_data", f"SELECT AVG({UNSIGNED}) FROM inverter_data"),
    "بیشترین توان راکتیو اینورتر چقدر بوده؟": ("inverter_data", f"SELECT MAX({UNSIGNED}) FROM inverter_data"),
    "مصرف پنل فشار ضعیف چقدر است؟": ("lvpanel_data", "SELECT AVG(tot_active_pow) FROM lvpanel_data"),
    "تولید انرژی روز آخر اینورتر چقدر بوده؟": (
        "inverter_data", "SELECT device_code, daily_pow_yield FROM inverter_data ORDER BY timestamp DESC LIMIT 1"),
    "آخرین توان اکتیو پنل فشار متوسط چقدر است؟": (
        "mvpanel_data", "SELECT timestamp, tot_active_pow FROM mvpanel_data ORDER BY timestamp DESC LIMIT 1"),
    "کمترین ولتاژ استرینگ‌ها که صفر نباشد چقدر است؟": (
        "string_data", "SELECT MIN(voltage) FROM string_data WHERE voltage > 0"),
    "چند رکورد اینورتر در حالت کاری Standby ثبت شده است؟": (
        "inverter_data", "SELECT COUNT(*) FROM inverter_data WHERE work_state = 'Standby'"),
    "در چند رکورد اینورتر، mccb برابر no_conn بوده است؟": (
        "inverter_data", "SELECT COUNT(*) FROM inverter_data WHERE mccb = 'no_conn'"),
    "لیست خطاهای رخ داده در اینورترها را نشان بده": (
        "inverter_data", "SELECT timestamp, device_code, fa_al_code FROM inverter_data WHERE fa_al_code <> 0"),
    "تابش خورشید امروز چقدر بوده است؟": None,
}


def golden() -> list[dict]:
    return yaml.safe_load((DEMO_MYSQL / "golden_questions.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def agent() -> MySQLAgent:
    uri = config.env_value("MYSQL_URI")
    if not uri:
        pytest.skip("RASAM_MYSQL_URI در `.env` نیست.")
    candidate = MySQLAgent(Secret(uri), "solar_telemetry", TABLES)
    try:
        candidate.list_sources()
    except pymysql.MySQLError:
        pytest.skip("MySQL محلی در دسترس نیست.")
    return candidate


# --- هم‌ارزی فایل‌ها -----------------------------------------------------------

def test_the_golden_questions_are_byte_for_byte_the_same_as_demos():
    """هدف همین است: همان سوال‌ها با همان جواب‌ها؛ هر اختلافی تقصیر آداپتور است، نه داده."""
    assert ((DEMO / "golden_questions.yaml").read_bytes()
            == (DEMO_MYSQL / "golden_questions.yaml").read_bytes())


def test_there_is_a_correct_sql_for_every_golden_question():
    assert [item["question"] for item in golden()] == list(GOLDEN_SQL)


def test_the_documentation_speaks_sql_not_mongo():
    text = (DEMO_MYSQL / "documentation.md").read_text(encoding="utf-8")
    for mongo_word in ("$group", "$match", "$sort", "$limit", "$avg", "pipeline", "aggregation"):
        assert mongo_word not in text
    assert "CASE WHEN tot_reactive_pow >= 2147483648" in text


def test_the_two_customers_share_no_connection_variable():
    """هر مشتری اتصال خودش را دارد؛ چیزی نیست که یکی را به دیتابیس دیگری ببرد."""
    demo = yaml.safe_load((DEMO / "profile.yaml").read_text(encoding="utf-8"))
    mysql = yaml.safe_load((DEMO_MYSQL / "profile.yaml").read_text(encoding="utf-8"))
    assert demo["connection_env"] != mysql["connection_env"] and mysql["db_type"] == "mysql"


# --- ۱) سقف کیفیت: SQLِ درست از مسیر واقعی ----------------------------------

@pytest.mark.parametrize("item", golden(), ids=lambda item: item["question"][:28])
def test_the_correct_sql_for_each_golden_question_grades_ok_through_the_real_path(agent, item):
    entry = GOLDEN_SQL[item["question"]]
    if entry is None:  # بیرون از دیتابیس: مدل باید جمله‌ی فارسی بدهد
        answer = Answer(question=item["question"], message="این داده در دیتابیس نیست.")
    else:
        source, sql = entry
        checked = agent.validate_query(source, sql)
        assert checked.ok, checked.reason
        rows = agent.execute(source, checked)
        answer = Answer(question=item["question"], source=source, query=checked.query, rows=rows)
    status, note = grade(item["expect"], answer)
    assert status == "ok", note


def test_every_example_of_the_customer_executes_on_the_real_database(agent):
    examples = yaml.safe_load((DEMO_MYSQL / "examples.yaml").read_text(encoding="utf-8"))
    for example in examples:
        checked = agent.validate_query(example["source"], example["query"])
        assert checked.ok, f"{example['question']}: {checked.reason}"
        agent.execute(example["source"], checked)  # خطای اجرا نباید بدهد


# --- ۲) مسیر کامل گراف، در پروسه‌ی خودش --------------------------------------

SCRIPT = r'''
import json, sys
from rasam.core import graph, llm

prompts, replies = [], json.loads(sys.argv[1])

def fake_ask(prompt):
    prompts.append(prompt)
    if prompt.startswith("You summarize"):
        return llm.Result(ok=True, text="میانگین دما ۲۸٫۶ درجه است.", reason="")
    return llm.Result(ok=True, text=replies.pop(0), reason="")

graph.llm.ask = fake_ask
answer = graph.answer("میانگین دمای داخلی اینورترها چقدر است؟")
print(json.dumps({
    "source": answer.source, "query": answer.query, "rows": answer.rows, "summary": answer.summary,
    "repaired": answer.repaired, "error": answer.error, "message": answer.message,
    "first_prompt": prompts[0], "all_prompts": prompts,
}, ensure_ascii=False, default=str))
'''


def run_graph(*model_replies: str) -> dict:
    env = {**os.environ, "RASAM_CUSTOMER": "demo-mysql", "PYTHONUTF8": "1"}
    done = subprocess.run([sys.executable, "-c", SCRIPT, json.dumps(list(model_replies))],
                          cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                          timeout=120)
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout.strip().splitlines()[-1])


GOOD = json.dumps({"table": "inverter_data",
                   "sql": "SELECT AVG(int_temp) AS avg_temp FROM inverter_data"})


def test_the_whole_graph_answers_on_mysql_with_a_scripted_model(agent):
    result = run_graph(GOOD)
    assert result["error"] is None and result["message"] is None
    assert result["source"] == "inverter_data"
    assert result["query"] == "SELECT AVG(int_temp) AS avg_temp FROM inverter_data LIMIT 1000"
    assert result["rows"][0]["avg_temp"] == pytest.approx(28.6077, abs=1e-3)
    assert result["summary"] == "میانگین دما ۲۸٫۶ درجه است."


def test_the_prompt_the_model_sees_is_sql_flavoured_and_never_mongo(agent):
    prompt = run_graph(GOOD)["first_prompt"]
    assert "MySQL" in prompt and "Table: inverter_data" in prompt
    assert "CASE WHEN tot_reactive_pow >= 2147483648" in prompt  # دانش SQLِ همین مشتری
    assert '"table"' in prompt and '"sql"' in prompt
    for mongo_word in ("$group", "pipeline", "aggregation", "Collection:"):
        assert mongo_word not in prompt


def test_a_rejected_query_is_repaired_and_the_repair_still_goes_through_the_guard(agent):
    """مدل اول SLEEP می‌نویسد؛ گارد ردش می‌کند؛ ترمیم یک SELECT سالم می‌دهد."""
    bad = json.dumps({"table": "inverter_data", "sql": "SELECT SLEEP(5) FROM inverter_data"})
    result = run_graph(bad, GOOD)
    assert result["repaired"] is True and result["error"] is None
    assert any("===Your previous attempt failed" in p and "SLEEP" in p for p in result["all_prompts"])


def test_a_query_that_keeps_failing_ends_as_an_error_and_never_reaches_the_database(agent):
    bad = json.dumps({"table": "inverter_data", "sql": "DROP TABLE inverter_data"})
    result = run_graph(bad, bad)
    assert result["error"] and result["rows"] == []
    with agent._connect() as conn, conn.cursor() as cursor:  # جدول هنوز هست
        cursor.execute("SELECT COUNT(*) AS n FROM `inverter_data`")
        assert cursor.fetchone()["n"] == 10161
