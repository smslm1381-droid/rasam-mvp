"""تست‌های گارد — قلب امنیتی محصول. بدون دیتابیس و بدون مدل زبانی.

این تست‌ها مهم‌ترین تست‌های پروژه‌اند: هر چیزی که از اینجا رد شود، روی دیتابیس
مشتری اجرا می‌شود. حمله‌های واقعی‌ای که اینجا نوشته شده‌اند همان‌هایی هستند که
در بخش ۴ نقشه به‌عنوان مدل تهدید ثبت شده‌اند.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from rasam import config
from rasam.databases.mongodb import guard

COLLECTIONS = {"inverter_data", "lvpanel_data", "mvpanel_data", "string_data"}


def run(pipeline, collection="inverter_data", **kwargs):
    return guard.check(pipeline, collection, COLLECTIONS, **kwargs)


# --- کوئری‌های سالم باید رد شوند --------------------------------------------

def test_simple_aggregation_passes():
    result = run([{"$group": {"_id": None, "avg": {"$avg": "$int_temp"}}}])
    assert result.ok and result.reason == ""


def test_realistic_multi_stage_query_passes():
    """همان الگویی که سوال «آخرین/امروز» تولید می‌کند."""
    result = run([
        {"$match": {"work_state": "Run", "timestamp": {"$gte": 1780000000}}},
        {"$group": {"_id": "$device_code", "peak": {"$max": "$daily_pow_yield"}}},
        {"$sort": {"peak": -1}},
        {"$limit": 5},
    ])
    assert result.ok


def test_computed_expressions_are_allowed():
    """فهرست اپراتورها باید نسبت به محاسبات سخاوتمند باشد."""
    result = run([{"$addFields": {"kw": {"$cond": [
        {"$gt": ["$tot_active_pow", 0]}, {"$divide": ["$tot_active_pow", 1000]}, 0]}}}])
    assert result.ok


# --- اجرای کد روی سرور دیتابیس ---------------------------------------------

def test_where_nested_inside_match_is_rejected():
    """`$where` چند لایه تودرتو — بازبینیِ فقط سطح اول این را نمی‌گیرد."""
    result = run([{"$match": {"$and": [{"status": "ON"}, {"$where": "sleep(9999)"}]}}])
    assert not result.ok
    assert "$where" in result.reason


def test_function_inside_group_is_rejected():
    result = run([{"$group": {"_id": None, "x": {
        "$function": {"body": "function(){return 1}", "args": [], "lang": "js"}}}}])
    assert not result.ok
    assert "$function" in result.reason


def test_accumulator_is_rejected():
    result = run([{"$group": {"_id": None, "x": {"$accumulator": {"init": "function(){}"}}}}])
    assert not result.ok


# --- دقت پیام رد ------------------------------------------------------------

def test_forbidden_operator_says_forbidden_and_why():
    """«ممنوع» یعنی هرگز مجاز نمی‌شود — پیام باید دلیل امنیتی‌اش را بگوید."""
    reason = run([{"$match": {"$where": "1"}}]).reason
    assert "در فهرست ممنوع است" in reason
    assert "جاوااسکریپت" in reason


def test_write_stage_says_why_it_is_forbidden():
    reason = run([{"$match": {}}, {"$out": "x"}]).reason
    assert "نوشتن" in reason


def test_unlisted_operator_is_not_called_forbidden():
    """`$rand` خطرناک نیست، فقط شناخته‌شده نیست. نباید «ممنوع» خوانده شود."""
    reason = run([{"$addFields": {"r": {"$rand": {}}}}]).reason
    assert "در فهرست مجاز نیست" in reason
    assert "ممنوع" not in reason


def test_message_says_whether_it_was_a_stage_or_an_operator():
    """جای اصلاح در کوئری فرق می‌کند، پس پیام باید تفکیک کند."""
    assert run([{"$sample": {"size": 5}}]).reason.startswith("مرحله")
    assert run([{"$match": {"$rand": {}}}]).reason.startswith("عملگر")


# --- تبدیل خواندن به نوشتن --------------------------------------------------

def test_out_at_end_of_pipeline_is_rejected():
    result = run([{"$match": {"status": "ON"}}, {"$out": "stolen"}])
    assert not result.ok
    assert "$out" in result.reason


def test_merge_is_rejected():
    result = run([{"$match": {}}, {"$merge": {"into": "stolen"}}])
    assert not result.ok


# --- stageهایی که عمداً مجاز نیستند -----------------------------------------

@pytest.mark.parametrize("stage", [
    {"$lookup": {"from": "users", "localField": "a", "foreignField": "b", "as": "c"}},
    {"$facet": {"a": []}},
    {"$bucket": {"groupBy": "$int_temp", "boundaries": [0, 50]}},
    {"$skip": 10},
    {"$unionWith": "lvpanel_data"},
    {"$graphLookup": {"from": "x", "startWith": "$a", "connectFromField": "a",
                      "connectToField": "b", "as": "c"}},
])
def test_stages_outside_the_whitelist_are_rejected(stage):
    assert not run([stage]).ok


# --- ساختار بدریخت ----------------------------------------------------------

@pytest.mark.parametrize("pipeline", [
    [], "not a list", None, [{"$match": {}, "$limit": 5}], ["$match"], [{}],
])
def test_malformed_pipelines_are_rejected(pipeline):
    assert not run(pipeline).ok


def test_rejected_pipeline_is_none_not_the_original():
    """اگر فراخوان `ok` را چک نکند باید فوراً بشکند، نه اینکه کوئری خام اجرا شود."""
    result = run([{"$match": {"$where": "1"}}])
    assert result.query is None


# --- فهرست سفید کالکشن‌ها ---------------------------------------------------

def test_query_on_unlisted_collection_is_rejected():
    result = run([{"$match": {}}], collection="billing")
    assert not result.ok
    assert "billing" in result.reason


def test_query_on_listed_collection_passes():
    assert run([{"$match": {}}], collection="string_data").ok


# --- سقف‌ها -----------------------------------------------------------------

def test_row_limit_is_appended_when_configured(monkeypatch):
    """`Settings` غیرقابل‌تغییر است، پس کل نمونه عوض می‌شود نه یک فیلدش."""
    monkeypatch.setattr(config, "settings", replace(config.settings, max_rows=1000))
    result = run([{"$match": {"status": "ON"}}])
    assert result.query[-1] == {"$limit": 1000}


def test_row_limit_sits_after_everything_the_model_wrote(monkeypatch):
    """سقف باید آخر بنشیند، وگرنه stageهای بعدی می‌توانند از آن رد شوند."""
    monkeypatch.setattr(config, "settings", replace(config.settings, max_rows=10))
    result = run([{"$match": {}}, {"$limit": 99999}, {"$sort": {"int_temp": -1}}])
    assert result.query[-1] == {"$limit": 10}


def test_no_row_limit_is_added_when_switched_off(monkeypatch):
    """اگر تنظیم خاموش شود، گارد نباید سقف حدسی اضافه کند."""
    monkeypatch.setattr(config, "settings", replace(config.settings, max_rows=None))
    assert config.settings.max_rows is None
    result = run([{"$match": {"status": "ON"}}])
    assert result.query == [{"$match": {"status": "ON"}}]


def test_time_limit_travels_with_the_result():
    """سقف زمان از گارد بیرون می‌آید تا فراخوان نتواند فراموشش کند."""
    assert run([{"$match": {}}]).max_time_ms == config.settings.query_timeout_ms


# --- بیس دسترسی سطری --------------------------------------------------------

def test_row_filter_is_injected_at_the_front():
    """شرط سطری باید *اول* بنشیند تا هیچ stage بعدی نتواند دورش بزند."""
    result = run([{"$match": {"status": "ON"}}], row_filter={"plant_id": 3})
    assert result.query[0] == {"$match": {"plant_id": 3}}


def test_without_a_row_filter_nothing_is_injected():
    result = run([{"$match": {"status": "ON"}}])
    assert result.query[0] == {"$match": {"status": "ON"}}


@pytest.mark.parametrize("collection", [["inverter_data"], {"a": 1}, 5, None, b"x"])
def test_a_collection_that_is_not_a_string_is_rejected_not_a_crash(collection):
    """نام کالکشن را مدل می‌نویسد؛ فهرست بودنش قبلاً `TypeError: unhashable` می‌داد.

    آزمون انطباق پیدایش کرد. گارد هرگز استثنا نمی‌دهد (قاعده‌ی ۷).
    """
    result = guard.check([{"$match": {}}], collection, {"inverter_data"})
    assert result.ok is False and result.query is None
