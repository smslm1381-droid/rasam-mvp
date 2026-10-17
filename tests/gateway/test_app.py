"""قرارداد HTTP واسط؛ SQL سهمیه جداگانه روی شبیه‌ساز واقعی D1 سنجیده می‌شود."""

from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from gateway import app as gateway_app, licenses, upstream
from rasam.core import llm

KEY = "test-license-key-with-enough-entropy"
BODY = {"model": "untrusted-expensive-model", "messages": [{"role": "user", "content": "private-question"}]}


class BoundApp:
    def __init__(self, env):
        self.env = env
    async def __call__(self, scope, receive, send):
        scope["env"] = self.env
        await gateway_app.app(scope, receive, send)


@pytest.fixture
def gateway(monkeypatch):
    state = {"reason": None, "calls": [], "reserves": 0}
    async def reserve(self, key, now=None):
        state["reserves"] += 1
        assert key == KEY
        return ({"used": 1}, None) if state["reason"] is None else (None, state["reason"])
    async def chat(env, payload):
        state["calls"].append(payload)
        return {"choices": [{"message": {"role": "assistant", "content": "answer"}}]}
    monkeypatch.setattr(licenses.Licenses, "reserve", reserve)
    monkeypatch.setattr(upstream, "chat", chat)
    env = SimpleNamespace(DB=object(), UPSTREAM_MODEL="server-selected-model", UPSTREAM_MAX_TOKENS="1200")
    client = TestClient(BoundApp(env), headers={"Authorization": "Bearer " + KEY})
    return client, state


def test_success_uses_server_model_and_clamps_tokens_without_logging_content(gateway, capsys, caplog):
    client, state = gateway
    response = client.post("/v1/chat/completions", json={**BODY, "max_tokens": 10000})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert state["calls"][0]["model"] == "server-selected-model"
    assert state["calls"][0]["max_tokens"] == 1200
    assert "private-question" not in capsys.readouterr().out + caplog.text


@pytest.mark.parametrize("code,status", [("license_invalid", 401), ("license_revoked", 403),
    ("license_expired", 402), ("quota_exceeded", 429)])
def test_license_errors_are_distinct_and_never_call_model(gateway, code, status):
    client, state = gateway
    state["reason"] = code
    response = client.post("/v1/chat/completions", json=BODY)
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert state["calls"] == []
    failure = RuntimeError("private-driver-error")
    failure.body = response.json()
    failure.status_code = status
    assert llm._describe_failure(failure) == licenses.ERRORS[code][1]


def test_missing_or_malformed_license_never_uses_database(gateway):
    client, state = gateway
    assert client.post("/v1/chat/completions", json=BODY, headers={"Authorization": ""}).status_code == 401
    assert state["reserves"] == 0


@pytest.mark.parametrize("body", [{}, {**BODY, "stream": True}, {**BODY, "messages": []},
    {**BODY, "messages": [{"role": "tool", "content": "x"}]}, {**BODY, "max_tokens": -1},
    {**BODY, "temperature": 5}, {**BODY, "messages": [{"role": "user", "content": {"secret": "x"}}]}])
def test_invalid_requests_do_not_consume_quota_or_echo_input(gateway, body):
    client, state = gateway
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 400 and state["reserves"] == 0
    assert "private-question" not in response.text


def test_size_limit_applies_before_quota(gateway):
    client, state = gateway
    response = client.post("/v1/chat/completions", content=b"x" * 512001)
    assert response.status_code == 413 and state["reserves"] == 0


def test_upstream_failure_never_reveals_provider_error(gateway, monkeypatch):
    client, state = gateway
    async def failed(*args):
        return None
    monkeypatch.setattr(upstream, "chat", failed)
    assert client.post("/v1/chat/completions", json=BODY).status_code == 503


def test_raw_database_exception_is_never_echoed(gateway, monkeypatch):
    client, state = gateway
    async def failed(*args):
        raise RuntimeError("private-db-credential")
    monkeypatch.setattr(licenses.Licenses, "reserve", failed)
    response = client.post("/v1/chat/completions", json=BODY)
    assert response.status_code == 503 and "private-db-credential" not in response.text
