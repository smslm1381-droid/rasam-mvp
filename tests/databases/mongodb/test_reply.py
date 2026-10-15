"""تست خواندن پاسخ مدل برای MongoDB — بدون شبکه و بدون دیتابیس."""

from __future__ import annotations

import pytest

from rasam.databases.mongodb.reply import parse_reply


@pytest.mark.parametrize("text, kind", [
    ('{"collection": "a", "pipeline": []}', "query"),
    ("این داده موجود نیست.", "message"),
    ("[1, 2, 3]", "error"),             # JSON هست ولی شیء نیست
    ('{"collection": "a"}}', "query"),  # آکولاد اضافه، قابل نجات
    ("", "message"),
])
def test_a_broken_query_is_never_mistaken_for_a_persian_sentence(text, kind):
    """تا دیروز JSON نصفه‌نیمه به‌عنوان «جواب» به کاربر نشان داده می‌شد."""
    reply = parse_reply(text)
    assert (reply.query is not None or reply.source is not None) is (kind == "query")
    assert (reply.message is not None) is (kind == "message")
    assert (reply.error is not None) is (kind == "error")


def test_the_model_keys_are_mapped_to_the_generic_names():
    reply = parse_reply('{"collection": "inverter_data", "pipeline": [{"$match": {}}]}')
    assert reply.source == "inverter_data"
    assert reply.query == [{"$match": {}}]


@pytest.mark.parametrize("text", [
    '{"collection": "inverter_data", "pipeline": [{"$match": {}}]}}',   # آکولاد اضافه
    'بله:\n{"collection": "inverter_data", "pipeline": [{"$match": {}}]}\nتمام.',
    '{"collection": "inverter_data", "pipeline": [{"$match": {}}]} thinking done',
    '```json\n{"collection": "inverter_data", "pipeline": [{"$match": {}}]}\n```',
])
def test_a_valid_query_is_not_thrown_away_because_of_extra_text(text):
    """مدل‌های واقعی گاهی بعد از JSON چیز اضافه می‌گذارند.

    دور ریختن یک کوئریِ درست به‌خاطر یک `}` زیادی، هزینه‌ی بی‌دلیل است — و آنچه
    بیرون کشیده می‌شود باز هم از گارد رد می‌شود.
    """
    reply = parse_reply(text)
    assert reply.source == "inverter_data" and reply.query == [{"$match": {}}]
    assert reply.error is None and reply.message is None


def test_a_brace_inside_a_string_does_not_confuse_the_extraction():
    reply = parse_reply('{"collection": "a", "note": "}{", "pipeline": []}}')
    assert reply.source == "a" and reply.error is None


def test_an_unfinished_object_is_an_error():
    assert parse_reply('{"collection": "a", "pipeline": [').error is not None
