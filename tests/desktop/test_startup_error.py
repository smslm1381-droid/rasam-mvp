"""گزارش شکست اجرا باید قابل بررسی باشد و هیچ متن یا راز استثنا را ننویسد."""

import json

from rasam.desktop import launcher, startup_error


def test_startup_failure_records_location_without_exception_message(tmp_path, monkeypatch):
    secret = "private-model-key-and-session-token"

    def fail(open_browser):
        raise PermissionError(13, secret)

    monkeypatch.setattr(launcher.config, "DATA_HOME", tmp_path)
    monkeypatch.setattr(launcher, "serve", fail)
    messages = []
    monkeypatch.setattr(launcher, "show_error", messages.append)
    assert launcher.main([]) == 1
    path = tmp_path / "startup-error.json"
    text = path.read_text(encoding="utf-8")
    report = json.loads(text)
    assert report["error"] == "PermissionError"
    assert report["errno"] == 13
    assert report["frames"][-1]["function"] == "fail"
    assert secret not in text and secret not in messages[0]
    assert str(path) in messages[0]


def test_failure_to_write_report_does_not_hide_original_failure(tmp_path, monkeypatch):
    blocked = tmp_path / "file"
    blocked.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(launcher.config, "DATA_HOME", blocked)

    def fail(open_browser):
        raise RuntimeError("private connection string")

    monkeypatch.setattr(launcher, "serve", fail)
    messages = []
    monkeypatch.setattr(launcher, "show_error", messages.append)
    assert launcher.main([]) == 1
    assert len(messages) == 1
    assert "private connection string" not in messages[0]


def test_report_keeps_only_the_latest_failure(tmp_path):
    startup_error.record_error(tmp_path, RuntimeError("old secret"))
    path = startup_error.record_error(tmp_path, ValueError("new secret"))
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["error"] == "ValueError"
    assert report["frames"] == []
    assert "secret" not in path.read_text(encoding="utf-8")
