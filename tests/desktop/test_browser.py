"""بازکردن مجدد نباید تب موجود را بازسازی کند یا صفحهٔ دیگری را جابه‌جا کند."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rasam.desktop import browser


def test_existing_page_does_not_open_another_tab(monkeypatch):
    monkeypatch.setattr(browser, "focus_existing", lambda url: True)
    opened = Mock()
    monkeypatch.setattr(browser.webbrowser, "open", opened)
    browser.open_page("http://127.0.0.1:43210/?token=test")
    opened.assert_not_called()


def test_closed_page_opens_again(monkeypatch):
    monkeypatch.setattr(browser, "focus_existing", lambda url: False)
    opened = Mock()
    monkeypatch.setattr(browser.webbrowser, "open", opened)
    url = "http://127.0.0.1:43210/?token=test"
    browser.open_page(url)
    opened.assert_called_once_with(url)


@pytest.mark.skipif(browser.sys.platform != "darwin", reason="مرورگر بومی مک لازم است")
@pytest.mark.parametrize("output,code,expected", [("found\n", 0, True), ("missing\n", 0, False), ("", 1, False)])
def test_mac_uses_only_the_current_session_origin(monkeypatch, output, code, expected):
    monkeypatch.setattr(browser, "_default_mac_browser", lambda url: "com.google.Chrome")
    run = Mock(return_value=SimpleNamespace(returncode=code, stdout=output))
    monkeypatch.setattr(browser.subprocess, "run", run)
    assert browser.focus_existing("http://127.0.0.1:43210/?token=secret") is expected
    script = run.call_args.kwargs["input"]
    assert 'http://127.0.0.1:43210/' in script
    assert "secret" not in script
    assert "set URL" not in script


@pytest.mark.skipif(browser.sys.platform != "darwin", reason="مرورگر بومی مک لازم است")
def test_browser_timeout_does_not_crash_launcher(monkeypatch):
    monkeypatch.setattr(browser, "_default_mac_browser", lambda url: "com.google.Chrome")
    def timeout(*args, **kwargs):
        raise browser.subprocess.TimeoutExpired("osascript", 5)
    monkeypatch.setattr(browser.subprocess, "run", timeout)
    assert not browser.focus_existing("http://127.0.0.1:43210/")
