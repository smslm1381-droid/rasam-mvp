"""بستهٔ Worker فقط منبع سرور است؛ فایل محیط، ابزار و داده همراهش نمی‌رود."""

import pytest
from gateway import build_worker


def test_worker_bundle_has_only_explicit_server_sources(tmp_path):
    folder = build_worker.build(tmp_path / "bundle")
    files = {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}
    assert files == {"worker.py", "gateway/__init__.py", "gateway/app.py", "gateway/licenses.py", "gateway/upstream.py"}


def test_unknown_file_in_build_output_stops_packaging_without_deleting_it(tmp_path):
    folder = tmp_path / "bundle"
    folder.mkdir()
    secret = folder / ".dev.vars"
    secret.write_text("test-only", encoding="utf-8")
    with pytest.raises(ValueError):
        build_worker.build(folder)
    assert secret.read_text() == "test-only"


def test_identical_build_does_not_trigger_worker_reload_by_touching_sources(tmp_path):
    folder = build_worker.build(tmp_path / "bundle")
    before = {path: path.stat().st_mtime_ns for path in folder.rglob("*") if path.is_file()}
    build_worker.build(folder)
    assert {path: path.stat().st_mtime_ns for path in before} == before
