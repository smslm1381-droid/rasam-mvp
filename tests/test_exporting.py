"""تست خروجی CSV و Excel، بدون دیتابیس و مدل."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ask  # noqa: E402
import exporting  # noqa: E402
from graph import Answer  # noqa: E402


ROWS = [{"device": "in1", "avg": 28.6}, {"device": "in2", "max": 31.2}]


def test_csv_contains_all_columns_and_rows():
    assert exporting.to_csv(ROWS).splitlines() == [
        "device,avg,max", "in1,28.6,", "in2,,31.2"]


def test_excel_contains_all_columns_and_rows():
    workbook = load_workbook(io.BytesIO(exporting.to_excel(ROWS)))
    assert list(workbook.active.values) == [
        ("device", "avg", "max"), ("in1", 28.6, None), ("in2", None, 31.2)]


def test_cli_writes_requested_csv(monkeypatch, tmp_path):
    path = tmp_path / "result.csv"
    monkeypatch.setattr(ask, "answer", lambda _: Answer(question="q", rows=ROWS))
    assert ask.main(["--csv", str(path), "q"]) == 0
    assert path.read_text(encoding="utf-8") == exporting.to_csv(ROWS)