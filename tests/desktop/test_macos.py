"""رویدادهای بومی مک باید صفحه را باز کنند و خروج امن سرور را حفظ کنند."""

import sys
from types import SimpleNamespace

import pytest

if sys.platform != "darwin":
    pytest.skip("رویداد AppKit فقط روی مک اجرا می‌شود.", allow_module_level=True)

from rasam.desktop import macos
from rasam.desktop.instance import DesktopInstance


@pytest.fixture
def delegate(tmp_path, monkeypatch):
    monkeypatch.setattr(macos.config, "DATA_HOME", tmp_path)
    item = macos.ApplicationDelegate.alloc().init()
    item.finished = False
    return item


def test_dock_reopen_uses_the_existing_validated_session(delegate, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(macos, "open_page", lambda url: opened.append(url))
    instance = DesktopInstance(tmp_path)
    assert instance.acquire()
    try:
        url = instance.publish(43123, "a" * 40)
        assert delegate.applicationShouldHandleReopen_hasVisibleWindows_(None, False) is False
        assert opened == [url]
        (tmp_path / ".desktop-session.json").write_text('{"port":"https://bad","token":"bad"}')
        delegate.applicationShouldHandleReopen_hasVisibleWindows_(None, False)
        assert opened == [url]
    finally:
        instance.close()


def test_dock_quit_requests_authenticated_shutdown_before_native_exit(delegate, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(macos.httpx, "post", lambda url, **kwargs: calls.append((url, kwargs)))
    instance = DesktopInstance(tmp_path)
    assert instance.acquire()
    try:
        instance.publish(43123, "a" * 40)
        assert delegate.applicationShouldTerminate_(None) == macos.AppKit.NSTerminateCancel
        assert calls[0][0] == "http://127.0.0.1:43123/shutdown"
        assert calls[0][1]["headers"]["X-Rasam-Token"] == "a" * 40
        assert calls[0][1]["trust_env"] is False
        delegate.finished = True
        assert delegate.applicationShouldTerminate_(None) == macos.AppKit.NSTerminateNow
        assert len(calls) == 1
    finally:
        instance.close()


@pytest.mark.parametrize("fails", [False, True])
def test_server_exit_or_failure_closes_the_native_loop(delegate, monkeypatch, fails):
    ended = []
    delegate.application = SimpleNamespace(terminate_=lambda value: ended.append(True))
    def serve():
        if fails:
            raise RuntimeError("private-data")
        return 0
    delegate.serve = serve
    monkeypatch.setattr(macos.AppHelper, "callAfter", lambda callback, value: callback(value))
    delegate.runServer()
    assert delegate.finished and ended == [True]
    assert delegate.result == int(fails)
