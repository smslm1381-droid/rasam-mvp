"""تست بازیابی معنایی فارسی از شاخص مشتری."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge_store import KnowledgeStore  # noqa: E402


def test_persian_inverter_question_retrieves_the_inverter_schema(tmp_path):
    store = KnowledgeStore("demo", tmp_path / "chroma")
    schema = (
        "Collection: inverter_data\n"
        "  int_temp: float e.g. 25\n\n"
        "Collection: mvpanel_data\n"
        "  voltage_a: float e.g. 220"
    )
    store.rebuild(schema, Path(__file__).resolve().parents[1] / "knowledge")
    retrieved = store.retrieve("دمای اینورترها", limit=1)
    assert "inverter_data" in retrieved["schema"]
    assert "mvpanel_data" not in retrieved["schema"]