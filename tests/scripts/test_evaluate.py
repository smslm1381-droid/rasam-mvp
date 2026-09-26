"""تست‌های سنجه‌ی کیفیت — بدون شبکه و بدون دیتابیس.

سنجه‌ای که خودش اشتباه نمره بدهد، بدتر از نداشتن سنجه است: باعث می‌شود پرامپت
سالم را «خراب» اعلام کنیم و دنبال اصلاح چیزی برویم که خراب نیست. پس خودِ
نمره‌دهی هم تست دارد.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rasam.core.graph import Answer
from scripts.evaluate import QUESTIONS_FILE, grade

QUESTIONS = yaml.safe_load(QUESTIONS_FILE.read_text(encoding="utf-8"))

PIPE = [{"$group": {"_id": None, "v": {"$avg": "$int_temp"}}}]


def answered(rows) -> Answer:
    return Answer(question="q", collection="inverter_data", pipeline=PIPE, rows=rows)


# --- جواب عددی --------------------------------------------------------------

def test_a_matching_number_passes():
    assert grade({"value": 28.61}, answered([{"avg_temp": 28.61}]))[0] == "ok"


def test_the_column_name_does_not_matter():
    """مدل نام ستون را خودش انتخاب می‌کند، پس نباید رویش حساب کرد."""
    for name in ("v", "avg_temp", "average_internal_temperature", "میانگین"):
        assert grade({"value": 28.61}, answered([{name: 28.61}]))[0] == "ok"


def test_a_wrong_number_fails():
    status, note = grade({"value": 28.61}, answered([{"v": 999.0}]))
    assert status == "wrong" and "999" in note


def test_tolerance_is_respected():
    assert grade({"value": 28.61, "tolerance": 0.5}, answered([{"v": 28.9}]))[0] == "ok"
    assert grade({"value": 28.61, "tolerance": 0.01}, answered([{"v": 28.9}]))[0] == "wrong"


def test_an_extra_column_does_not_hide_the_answer():
    """رگرسیون واقعی.

    نسخه‌ی اول «اولین عدد ردیف» را می‌گرفت، و سوال «آخرین توان اکتیو» را غلط
    اعلام می‌کرد چون کوئریِ درست `timestamp` را هم برمی‌گرداند و اول می‌آمد.
    سنجه‌ای که کوئری درست را رد کند، بی‌فایده است.
    """
    row = {"timestamp": 1780918982, "tot_active_pow": 9.6}
    assert grade({"value": 9.6}, answered([row]))[0] == "ok"


def test_the_group_key_is_never_mistaken_for_the_answer():
    assert grade({"value": 592.8}, answered([{"_id": "dev1", "produced": 592.8}]))[0] == "ok"


def test_a_named_field_can_be_demanded_when_the_row_is_ambiguous():
    row = {"tot_active_pow": 9.6, "tot_reactive_pow": 25}
    assert grade({"value": 25, "field": "tot_reactive_pow"}, answered([row]))[0] == "ok"
    assert grade({"value": 25, "field": "tot_active_pow"}, answered([row]))[0] == "wrong"


def test_a_row_without_numbers_fails():
    assert grade({"value": 1}, answered([{"name": "فقط متن"}]))[0] == "wrong"


# --- جواب متنی و نتیجه‌ی خالی -----------------------------------------------

def test_a_message_is_expected_and_given():
    answer = Answer(question="q", message="این داده موجود نیست.")
    assert grade({"message": True}, answer)[0] == "ok"


def test_building_a_query_when_a_message_was_expected_fails():
    """سوال بی‌ربط نباید کوئری بگیرد."""
    assert grade({"message": True}, answered([{"v": 1}]))[0] == "wrong"


def test_a_message_when_a_number_was_expected_fails():
    answer = Answer(question="q", message="نمی‌دانم.")
    assert grade({"value": 28.61}, answer)[0] == "wrong"


def test_an_empty_result_can_be_the_right_answer():
    assert grade({"empty": True}, answered([]))[0] == "ok"
    assert grade({"empty": True}, answered([{"v": 1}]))[0] == "wrong"


def test_an_unexpectedly_empty_result_fails():
    assert grade({"value": 28.61}, answered([]))[0] == "wrong"


# --- تفکیک «غلط» از «سنجیده نشد» -------------------------------------------

def test_a_service_failure_is_not_counted_as_a_wrong_answer():
    """اگر خطای سرویس «غلط» شمرده شود، درصد دروغ می‌گوید."""
    answer = Answer(question="q", error="سرویس مدل درخواست‌ها را محدود کرده است.")
    assert grade({"value": 28.61}, answer)[0] == "skipped"


def test_a_rejected_query_is_a_wrong_answer_not_a_skip():
    """مدل کوئری ساخته و گارد ردش کرده — این تقصیر مدل است، نه سرویس."""
    answer = Answer(question="q", pipeline=PIPE,
                    error="کوئری ساخته‌شده پذیرفته نشد: عملگر «$where» ...")
    assert grade({"value": 28.61}, answer)[0] == "wrong"


# --- خودِ فایل سوالات -------------------------------------------------------

def test_there_are_fifteen_golden_questions():
    assert len(QUESTIONS) == 15


@pytest.mark.parametrize("item", QUESTIONS, ids=[q["question"][:28] for q in QUESTIONS])
def test_every_question_has_exactly_one_acceptance_condition(item):
    expect = item["expect"]
    conditions = [k for k in ("value", "empty", "message") if k in expect]
    assert len(conditions) == 1, f"شرط پذیرش مبهم: {conditions}"
    assert item["question"].strip()
