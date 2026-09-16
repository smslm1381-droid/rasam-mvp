"""تست‌های لایه‌ی نمایش.

`ask.py` هیچ منطقی ندارد (قاعده‌ی امنیتی ۴)، پس اینجا فقط یک چیز سنجیده
می‌شود: سه حالتِ `Answer` باید سه جور متفاوت نمایش داده شوند.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ask  # noqa: E402
from graph import Answer  # noqa: E402


def test_an_error_is_labelled_as_one():
    out = ask.render(Answer(question="q", error="دیتابیس در دسترس نیست."), show_query=False)
    assert out.startswith("خطا:") and "دیتابیس در دسترس نیست." in out


def test_a_message_is_shown_plainly_without_the_error_label():
    """«این داده موجود نیست» جواب است، نه خطا — نباید مثل خطا دیده شود."""
    out = ask.render(Answer(question="q", message="این داده موجود نیست."), show_query=False)
    assert out == "این داده موجود نیست."


def test_rows_are_rendered_as_an_aligned_table():
    answer = Answer(question="q", rows=[{"device": "in1", "avg": 28.6},
                                        {"device": "in2", "avg": 31.25}])
    lines = ask.render(answer, show_query=False).splitlines()
    assert "device" in lines[0] and "avg" in lines[0]
    assert len(lines) == 4  # عنوان + خط جدا‌کننده + دو ردیف


def test_an_empty_result_is_explained_not_left_blank():
    out = ask.render(Answer(question="q", rows=[]), show_query=False)
    assert "هیچ ردیفی" in out


def test_the_query_is_hidden_unless_asked_for():
    answer = Answer(question="q", collection="inverter_data",
                    pipeline=[{"$match": {}}], rows=[{"n": 1}])
    assert "inverter_data" not in ask.render(answer, show_query=False)
    assert "inverter_data" in ask.render(answer, show_query=True)


def test_the_summary_is_shown_above_the_table():
    answer = Answer(question="q", rows=[{"avg": 28.6}], summary="میانگین ۲۸٫۶ است.")
    out = ask.render(answer, show_query=False)
    assert out.index("میانگین ۲۸٫۶ است.") < out.index("avg")


def test_without_a_summary_the_table_still_shows():
    out = ask.render(Answer(question="q", rows=[{"avg": 28.6}]), show_query=False)
    assert "avg" in out
