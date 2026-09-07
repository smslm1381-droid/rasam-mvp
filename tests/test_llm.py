"""تست‌های قدم ۵ — بدون هیچ تماس واقعی با شبکه.

مسیرهای شکست اینجا مهم‌ترند از مسیر موفقیت: وقتی سرویس بیرونی خراب می‌شود،
کاربر باید یک جمله‌ی فارسی ببیند نه stack trace. کلاینت جعلی جای مدل می‌نشیند
تا این مسیرها بدون خرج و بدون اینترنت امتحان شوند.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import llm  # noqa: E402


class FakeModel:
    """جای `ChatOpenAI` می‌نشیند: یا پاسخ می‌دهد یا خطای دلخواه پرتاب می‌کند."""

    def __init__(self, content: str = "", error: Exception | None = None):
        self.content = content
        self.error = error
        self.seen: list[str] = []

    def invoke(self, prompt: str):
        self.seen.append(prompt)
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content, text=self.content)


def use(monkeypatch, model: FakeModel) -> FakeModel:
    monkeypatch.setattr(llm, "_client", lambda: model)
    return model


def http_error(status: int) -> Exception:
    """خطای سرویس، همان‌طور که کتابخانه‌ی OpenAI می‌سازدش: با `status_code`."""
    error = RuntimeError(f"HTTP {status}")
    error.status_code = status
    return error


# --- مسیر سالم -------------------------------------------------------------

def test_successful_call_returns_the_text(monkeypatch):
    use(monkeypatch, FakeModel(content="کار می‌کنم"))
    result = llm.ask("سلام")
    assert result.ok and result.text == "کار می‌کنم" and result.reason == ""


def test_surrounding_whitespace_is_trimmed(monkeypatch):
    use(monkeypatch, FakeModel(content="\n  جواب  \n"))
    assert llm.ask("سلام").text == "جواب"


def test_the_prompt_reaches_the_model_unchanged(monkeypatch):
    """این فایل نباید پرامپت را دستکاری کند؛ ساختن پرامپت کار قدم ۶ است."""
    model = use(monkeypatch, FakeModel(content="ok"))
    llm.ask("میانگین دمای اینورترها؟")
    assert model.seen == ["میانگین دمای اینورترها؟"]


# --- پاسخ خالی --------------------------------------------------------------

@pytest.mark.parametrize("content", ["", "   ", "\n\t "])
def test_empty_response_becomes_a_clear_error(monkeypatch, content):
    """کشف نسخه‌ی ۱: مدل گاهی خالی برمی‌گرداند و باید همین‌جا گرفته شود."""
    use(monkeypatch, FakeModel(content=content))
    result = llm.ask("سلام")
    assert not result.ok
    assert "خالی" in result.reason


def test_empty_prompt_is_refused_without_calling_the_model(monkeypatch):
    model = use(monkeypatch, FakeModel(content="نباید صدا زده شود"))
    assert not llm.ask("   ").ok
    assert model.seen == []


# --- خطاهای سرویس ----------------------------------------------------------

@pytest.mark.parametrize("status, expected", [
    (401, "RASAM_LLM_API_KEY"),
    (402, "اعتبار"),
    (429, "محدود"),
    (404, "RASAM_LLM_MODEL"),
    (400, "RASAM_LLM_REASONING_EFFORT"),
])
def test_service_errors_become_actionable_persian_messages(monkeypatch, status, expected):
    use(monkeypatch, FakeModel(error=http_error(status)))
    result = llm.ask("سلام")
    assert not result.ok
    assert expected in result.reason


def test_server_side_errors_are_reported_as_temporary(monkeypatch):
    use(monkeypatch, FakeModel(error=http_error(503)))
    assert "در دسترس نیست" in llm.ask("سلام").reason


def test_connection_failure_points_at_the_likely_causes(monkeypatch):
    """بدون کد وضعیت یعنی پاسخی نرسیده — شبکه یا آدرس سرویس."""
    use(monkeypatch, FakeModel(error=ConnectionError("no route")))
    reason = llm.ask("سلام").reason
    assert "RASAM_LLM_BASE_URL" in reason
    assert "ConnectionError" in reason


def test_no_exception_ever_escapes(monkeypatch):
    """قاعده‌ی امنیتی ۷: خطا مقدار است، نه استثنا."""
    use(monkeypatch, FakeModel(error=ValueError("چیز غیرمنتظره")))
    assert llm.ask("سلام").ok is False


def test_failed_result_carries_no_text(monkeypatch):
    """مثل گارد: اگر فراخوان `ok` را چک نکند باید فوراً بشکند."""
    use(monkeypatch, FakeModel(error=http_error(401)))
    assert llm.ask("سلام").text is None


# --- حالت عیب‌یابی ----------------------------------------------------------

def test_verbose_prints_the_prompt_and_the_raw_response(monkeypatch, capsys):
    monkeypatch.setattr(config, "settings", replace(config.settings, verbose=True))
    use(monkeypatch, FakeModel(content="جواب مدل"))
    llm.ask("پرامپت آزمایشی")
    printed = capsys.readouterr().out
    assert "پرامپت آزمایشی" in printed
    assert "جواب مدل" in printed


def test_verbose_never_prints_the_api_key(monkeypatch, capsys):
    monkeypatch.setattr(config, "settings",
                        replace(config.settings, verbose=True, llm_api_key="SECRET-KEY-123"))
    use(monkeypatch, FakeModel(content="ok"))
    llm.ask("سلام")
    assert "SECRET-KEY-123" not in capsys.readouterr().out


def test_quiet_by_default(monkeypatch, capsys):
    monkeypatch.setattr(config, "settings", replace(config.settings, verbose=False))
    use(monkeypatch, FakeModel(content="ok"))
    llm.ask("سلام")
    assert capsys.readouterr().out == ""


# --- ساخت کلاینت از روی کانفیگ ---------------------------------------------

def test_thinking_is_off_by_default():
    """پیش‌فرض پروژه: فکرکردن خاموش. روی Gemini دو برابر و نیم سریع‌تر بود."""
    assert config.settings.llm_reasoning_effort == "none"


@pytest.mark.parametrize("effort", ["none", "low", "medium", "high"])
def test_thinking_level_reaches_the_client(monkeypatch, effort):
    """روشن‌کردنش در آینده باید فقط عوض‌کردن یک مقدار باشد، نه تغییر کد."""
    monkeypatch.setattr(config, "settings",
                        replace(config.settings, llm_reasoning_effort=effort))
    llm._client.cache_clear()
    assert llm._client().reasoning_effort == effort


def test_nothing_is_sent_when_the_service_does_not_know_the_parameter(monkeypatch):
    """راه فرار: سرویسی که این پارامتر را نشناسد با دیدنش ۴۰۰ می‌دهد."""
    monkeypatch.setattr(config, "settings",
                        replace(config.settings, llm_reasoning_effort=None))
    llm._client.cache_clear()
    assert llm._client().reasoning_effort is None


def test_limits_come_from_config_not_from_the_code(monkeypatch):
    monkeypatch.setattr(config, "settings",
                        replace(config.settings, llm_max_tokens=77, llm_temperature=0.4))
    llm._client.cache_clear()
    client = llm._client()
    assert client.max_tokens == 77 and client.temperature == 0.4


@pytest.fixture(autouse=True)
def _clear_client_cache():
    """کلاینت cache می‌شود، پس هر تست باید از حالت تمیز شروع کند."""
    llm._client.cache_clear()
    yield
    llm._client.cache_clear()


# --- سه حالت تنظیم فکرکردن، در سطح خواندن از محیط ------------------------

@pytest.mark.parametrize("raw, expected", [
    (None, "none"),          # تنظیم‌نشده → پیش‌فرض ما: خاموش
    ("none", "none"),
    ("high", "high"),
    ("unset", None),         # کلمه‌ی مخصوص: اصلاً فرستاده نشود
    ("UNSET", None),         # به بزرگی و کوچکی حرف حساس نیست
])
def test_reasoning_effort_is_read_from_the_environment(monkeypatch, raw, expected):
    monkeypatch.delenv("RASAM_LLM_REASONING_EFFORT", raising=False)
    if raw is not None:
        monkeypatch.setenv("RASAM_LLM_REASONING_EFFORT", raw)
    assert config._reasoning_effort() == expected


# --- سقف انتظار برای جواب مدل ----------------------------------------------

def test_request_timeout_is_set_not_left_to_the_library(monkeypatch):
    """پیش‌فرض کتابخانه ۱۰ دقیقه است — ۲۰۰ برابر زمان یک جواب واقعی."""
    monkeypatch.setattr(config, "settings",
                        replace(config.settings, llm_timeout_ms=90_000))
    llm._client.cache_clear()
    assert llm._client().request_timeout == 90.0


def test_timeout_is_configurable_in_milliseconds(monkeypatch):
    """کانفیگ میلی‌ثانیه نگه می‌دارد تا با بقیه‌ی سقف‌های پروژه هم‌واحد باشد."""
    monkeypatch.setattr(config, "settings",
                        replace(config.settings, llm_timeout_ms=5_000))
    llm._client.cache_clear()
    assert llm._client().request_timeout == 5.0
