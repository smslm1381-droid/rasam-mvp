"""تست بازیابی معنایی فارسی از شاخص مشتری."""

from __future__ import annotations

from rasam import config
from rasam.core.knowledge import KnowledgeStore


def test_persian_inverter_question_retrieves_the_inverter_schema(tmp_path):
    store = KnowledgeStore("demo", tmp_path / "chroma")
    schema = (
        "Collection: inverter_data\n"
        "  int_temp: float e.g. 25\n\n"
        "Collection: mvpanel_data\n"
        "  voltage_a: float e.g. 220"
    )
    store.rebuild(schema, config.CUSTOMERS_DIR / "demo")
    retrieved = store.retrieve("دمای اینورترها", limit=1)
    assert "inverter_data" in retrieved["schema"]
    assert "mvpanel_data" not in retrieved["schema"]


def test_knowledge_that_fits_the_budget_is_never_narrowed(tmp_path):
    """قاعده‌ی مهم قدم ۱۶: بازیابی نباید دانشی را که جا می‌شود حذف کند.

    روی داده‌ی واقعی دیده شد که برای «میانگین توان راکتیو اینورترها» هم schema
    اینورتر و هم تله‌ی `tot_reactive_pow` از پرامپت می‌افتادند — یعنی همان دو
    چیزی که جواب این سوال بی آن‌ها غلط است.
    """
    store = KnowledgeStore("demo", tmp_path / "chroma")
    store.rebuild("Collection: a\n  x: int", config.CUSTOMERS_DIR / "demo")
    full = {"schema": "s" * 10, "documentation": "d" * 10, "examples": "e" * 10}
    assert store.select("سوالی", full, budget=30) == full


def test_above_the_budget_the_index_narrows_the_knowledge(tmp_path):
    store = KnowledgeStore("demo", tmp_path / "chroma")
    schema = ("Collection: inverter_data\n  int_temp: float\n\n"
              "Collection: mvpanel_data\n  voltage_a: float")
    store.rebuild(schema, config.CUSTOMERS_DIR / "demo")
    full = {"schema": schema, "documentation": "d" * 100, "examples": "e" * 100}
    narrowed = store.select("دمای اینورترها", full, budget=10)
    assert narrowed != full
    assert "inverter_data" in narrowed["schema"]
