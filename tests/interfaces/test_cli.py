"""تست‌های لایه‌ی نمایش.

`rasam/cli.py` هیچ منطقی ندارد (قاعده‌ی امنیتی ۴)، پس اینجا فقط یک چیز سنجیده
می‌شود: سه حالتِ `Answer` باید سه جور متفاوت نمایش داده شوند.
"""

from __future__ import annotations

from pathlib import Path

from rasam import cli
from rasam.core.graph import Answer


def test_an_error_is_labelled_as_one():
    out = cli.render(Answer(question="q", error="دیتابیس در دسترس نیست."), show_query=False)
    assert out.startswith("خطا:") and "دیتابیس در دسترس نیست." in out


def test_a_message_is_shown_plainly_without_the_error_label():
    """«این داده موجود نیست» جواب است، نه خطا — نباید مثل خطا دیده شود."""
    out = cli.render(Answer(question="q", message="این داده موجود نیست."), show_query=False)
    assert out == "این داده موجود نیست."


def test_rows_are_rendered_as_an_aligned_table():
    answer = Answer(question="q", rows=[{"device": "in1", "avg": 28.6},
                                        {"device": "in2", "avg": 31.25}])
    lines = cli.render(answer, show_query=False).splitlines()
    assert "device" in lines[0] and "avg" in lines[0]
    assert len(lines) == 4  # عنوان + خط جدا‌کننده + دو ردیف


def test_an_empty_result_is_explained_not_left_blank():
    out = cli.render(Answer(question="q", rows=[]), show_query=False)
    assert "هیچ ردیفی" in out


def test_the_query_is_hidden_unless_asked_for():
    answer = Answer(question="q", source="inverter_data",
                    query=[{"$match": {}}], rows=[{"n": 1}])
    assert "inverter_data" not in cli.render(answer, show_query=False)
    assert "inverter_data" in cli.render(answer, show_query=True)


def test_the_summary_is_shown_above_the_table():
    answer = Answer(question="q", rows=[{"avg": 28.6}], summary="میانگین ۲۸٫۶ است.")
    out = cli.render(answer, show_query=False)
    assert out.index("میانگین ۲۸٫۶ است.") < out.index("avg")


def test_without_a_summary_the_table_still_shows():
    out = cli.render(Answer(question="q", rows=[{"avg": 28.6}]), show_query=False)
    assert "avg" in out


def test_the_null_group_key_column_is_not_shown():
    """`$group: {_id: null}` همیشه یک ستون `_id` خالی می‌سازد.

    جواب نیست، کلید گروه است. در جدول فقط شلوغی می‌کند — ولی حذفش *فقط* در
    نمایش است؛ `Answer.rows` و خروجی CSV و API دست‌نخورده می‌مانند.
    """
    answer = Answer(question="q", rows=[{"_id": None, "avg": 28.6}])
    out = cli.render(answer, show_query=False)
    assert "_id" not in out
    assert "28.6" in out
    assert answer.rows == [{"_id": None, "avg": 28.6}]


def test_a_missing_cell_is_left_blank_not_printed_as_none():
    answer = Answer(question="q", rows=[{"device": "in1", "avg": 28.6},
                                        {"device": "in2", "avg": None}])
    assert "None" not in cli.render(answer, show_query=False)


def test_columns_come_from_every_row_not_just_the_first():
    """در مونگو داکیومنت‌ها لزوماً فیلد یکسان ندارند."""
    answer = Answer(question="q", rows=[{"a": 1}, {"b": 2}])
    header = cli.render(answer, show_query=False).splitlines()[0]
    assert "a" in header and "b" in header
