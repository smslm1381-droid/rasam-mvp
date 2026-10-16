"""تست‌های سازگاری با ویندوز — روی مک هم اجرا می‌شوند و باید سبز باشند.

بیشتر مشکلات ویندوز را نمی‌شود روی مک دید، پس اینجا شرایطشان شبیه‌سازی می‌شود:
کنسولی که UTF-8 نیست، فایلی که Notepad با BOM ذخیره کرده، و پایان خط CRLF.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from rasam import console, customer
from rasam.core import exporting

ROOT = Path(__file__).resolve().parents[1]

PROFILE = """\
db_type: mongodb
connection_env: MONGO_URI
database: solar_telemetry
allowed_sources: [inverter_data]
capabilities: [summary]
limits: {max_rows: 1000}
"""


# --- کنسول -------------------------------------------------------------------

def test_a_cp1252_console_cannot_print_persian_until_use_utf8(monkeypatch):
    """همان خطای ویندوز: کنسول با کدگذاری محلی فارسی و ✅ را نمی‌پذیرد."""
    legacy = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", legacy)
    with pytest.raises(UnicodeEncodeError):
        print("✅ سلام")

    console.use_utf8()
    print("✅ سلام")
    sys.stdout.flush()
    assert sys.stdout.buffer.getvalue().decode("utf-8").strip().endswith("✅ سلام")


def test_use_utf8_never_crashes_on_a_stream_that_cannot_be_reconfigured(monkeypatch):
    """زیر pytest یا یک ابزار دیگر، جریان خروجی ممکن است `reconfigure` نداشته باشد."""
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    console.use_utf8()


def test_a_character_the_terminal_cannot_show_is_replaced_not_fatal(monkeypatch):
    legacy = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr(sys, "stdout", legacy)
    console.use_utf8()  # از این پس UTF-8 با جایگزینی
    print("سلام")


# --- BOM و پایان خط -----------------------------------------------------------

def write_profile(tmp_path: Path, raw: bytes) -> Path:
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "profile.yaml").write_bytes(raw)
    return tmp_path


def test_a_profile_saved_by_notepad_with_a_bom_still_loads(tmp_path):
    raw = b"\xef\xbb\xbf" + PROFILE.encode("utf-8")
    assert customer.load_profile("t", write_profile(tmp_path, raw)).database == "solar_telemetry"


def test_a_profile_with_windows_line_endings_loads(tmp_path):
    raw = PROFILE.replace("\n", "\r\n").encode("utf-8")
    assert customer.load_profile("t", write_profile(tmp_path, raw)).connection_env == "MONGO_URI"


def test_a_profile_with_both_bom_and_crlf_loads(tmp_path):
    raw = b"\xef\xbb\xbf" + PROFILE.replace("\n", "\r\n").encode("utf-8")
    assert customer.load_profile("t", write_profile(tmp_path, raw)).allowed_sources == {"inverter_data"}


def test_read_text_works_without_a_bom_too(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("سلام", encoding="utf-8")
    assert console.read_text(path) == "سلام"


def test_the_env_file_with_a_bom_and_crlf_needs_no_special_handling():
    """سنجیده شد، نه حدس: python-dotenv خودش BOM و CRLF را درست می‌خواند."""
    from dotenv import dotenv_values

    env = ROOT / "tests" / "_bom.env"
    env.write_bytes(b"\xef\xbb\xbfRASAM_FIRST=1\r\nRASAM_SECOND=2\r\n")
    try:
        assert dotenv_values(env, encoding="utf-8") == {"RASAM_FIRST": "1", "RASAM_SECOND": "2"}
    finally:
        env.unlink()


# --- Excel -------------------------------------------------------------------

def test_a_csv_file_opens_correctly_in_excel_with_persian(tmp_path):
    """Excel ویندوز فایل بدون BOM را با کدگذاری محلی باز می‌کند و فارسی خراب می‌شود."""
    path = tmp_path / "r.csv"
    exporting.write_csv([{"دستگاه": "اینورتر", "n": 1}], path)
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8-sig").splitlines() == ["دستگاه,n", "اینورتر,1"]


# --- مخزن --------------------------------------------------------------------

def test_the_repository_forces_lf_so_windows_checkouts_stay_byte_identical():
    """وگرنه با `core.autocrlf=true` آزمون «سوالات طلایی بایت‌به‌بایت یکی‌اند» می‌شکند."""
    rules = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in rules


def test_no_tracked_text_file_has_windows_line_endings():
    from subprocess import run

    files = run(["git", "ls-files", "*.py", "*.md", "*.yaml", "*.yml", "*.txt", "*.ini"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.split()
    if not files:
        pytest.skip("مخزن git نیست.")
    crlf = [name for name in files if b"\r\n" in (ROOT / name).read_bytes()]
    assert not crlf, f"پایان خط CRLF در: {crlf}"
