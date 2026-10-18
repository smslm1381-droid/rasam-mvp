"""عملیات واقعی D1؛ تکرار، هم‌زمانی، CSRF و نبود کد خام در پایگاه بررسی می‌شوند."""

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from admin_panel import mutations
from gateway import licenses
from tests.gateway.test_panel import panel, sign_in


def create_body(customer=None):
    return {"request_id": str(uuid4()), "customer": customer or "panel-" + uuid4().hex,
            "plan": "monthly", "daily_limit": 20}


def signed(panel):
    client, env = panel
    assert sign_in(client).status_code == 200
    return client, env, {"X-CSRF-Token": client.get("/api/me").json()["csrf"]}


def test_panel_lifecycle_uses_the_same_license_rules_and_writes_audit(panel):
    client, env, headers = signed(panel)
    body = create_body()
    created = client.post("/api/licenses/new", json=body, headers=headers)
    assert created.status_code == 200
    value = created.json()
    key, identifier = value["key"], value["license"]["identifier"]
    assert asyncio.run(licenses.Licenses(env.DB).status(key))["valid"] is True
    path = "/api/licenses/" + identifier
    renewed = client.post(path + "/extend", json={"request_id": str(uuid4()), "days": 10}, headers=headers)
    assert renewed.status_code == 200
    assert renewed.json()["license"]["expires_at"] == value["license"]["expires_at"] + 10 * 86400
    revoked = client.post(path + "/revoke", json={"request_id": str(uuid4())}, headers=headers)
    assert revoked.status_code == 200
    assert asyncio.run(licenses.Licenses(env.DB).status(key))["code"] == "license_revoked"
    events = client.get("/api/events")
    assert key not in events.text
    assert {event["action"] for event in events.json()["events"] if event["customer"] == body["customer"]} == {"new", "extend", "revoke"}


def test_request_replay_never_issues_or_extends_twice(panel):
    client, env, headers = signed(panel)
    body = create_body()
    first = client.post("/api/licenses/new", json=body, headers=headers).json()
    replay = client.post("/api/licenses/new", json=body, headers=headers).json()
    assert replay["replayed"] is True and replay["key"] is None
    assert first["license"]["identifier"] == replay["license"]["identifier"]
    extend = {"request_id": str(uuid4()), "days": 30}
    path = "/api/licenses/" + first["license"]["identifier"] + "/extend"
    one = client.post(path, json=extend, headers=headers).json()
    two = client.post(path, json=extend, headers=headers).json()
    assert one["license"]["expires_at"] == two["license"]["expires_at"]
    assert client.post("/api/licenses/new", json={**body, "customer": "different"}, headers=headers).status_code == 409


def test_concurrent_duplicate_issuance_creates_exactly_one_license_and_event(d1):
    async def run():
        body = create_body()
        results = await asyncio.gather(*(mutations.perform(d1, "test-actor", "new", body) for _ in range(4)))
        assert all(status == 200 for value, status in results)
        assert sum(value["key"] is not None for value, status in results) == 1
        identifiers = {value["license"]["identifier"] for value, status in results}
        assert len(identifiers) == 1
        count = await d1.prepare("SELECT COUNT(*) AS n FROM licenses WHERE customer = ?").bind(body["customer"]).first()
        assert count["n"] == 1
        count = await d1.prepare("SELECT COUNT(*) AS n FROM admin_operations WHERE request_id = ?").bind(body["request_id"]).first()
        assert count["n"] == 1
    asyncio.run(run())


def test_no_audit_means_no_license_change_on_transaction_failure(d1):
    class BrokenAudit:
        def prepare(self, sql):
            return d1.prepare(sql)
        async def batch(self, statements):
            return await d1.batch([statements[0], d1.prepare("INSERT INTO missing_audit_table VALUES (1)")])
    async def run():
        body = create_body()
        with pytest.raises(httpx.HTTPStatusError):
            await mutations.perform(BrokenAudit(), "test-actor", "new", body)
        row = await d1.prepare("SELECT COUNT(*) AS n FROM licenses WHERE customer = ?").bind(body["customer"]).first()
        assert row["n"] == 0
    asyncio.run(run())


def test_quota_change_does_not_reset_usage(panel):
    client, env, headers = signed(panel)
    created = client.post("/api/licenses/new", json=create_body(), headers=headers).json()
    identifier = created["license"]["identifier"]
    day = datetime.now(timezone.utc).date().isoformat()
    asyncio.run(env.DB.prepare("UPDATE licenses SET used = 7, usage_day = ? WHERE token_hash = ?").bind(day, identifier).run())
    response = client.post("/api/licenses/" + identifier + "/quota",
        json={"request_id": str(uuid4()), "daily_limit": 5}, headers=headers)
    assert response.status_code == 200
    assert response.json()["license"]["used_today"] == 7
    assert asyncio.run(licenses.Licenses(env.DB).reserve(created["key"]))[1] == "quota_exceeded"


def test_missing_session_csrf_or_origin_cannot_modify_licenses(panel):
    client, env = panel
    body = create_body()
    assert client.post("/api/licenses/new", json=body).status_code == 401
    assert client.get("/api/events").status_code == 401
    client, env, headers = signed(panel)
    assert client.post("/api/licenses/new", json=body).status_code == 403
    assert client.post("/api/licenses/new", json=body, headers={**headers, "Origin": "https://evil.example"}).status_code == 403
    result = asyncio.run(env.DB.prepare("SELECT COUNT(*) AS n FROM licenses WHERE customer = ?").bind(body["customer"]).first())
    assert result["n"] == 0


@pytest.mark.parametrize("daily_limit", [True, 0, -1, 100001, "20"])
def test_quota_cannot_bypass_server_validation(panel, daily_limit):
    client, env, headers = signed(panel)
    body = {**create_body(), "daily_limit": daily_limit}
    assert client.post("/api/licenses/new", json=body, headers=headers).status_code == 400


def test_raw_key_is_not_stored_in_license_or_audit_rows(panel):
    client, env, headers = signed(panel)
    body = create_body("name ' SQL <script>alert(1)</script>")
    response = client.post("/api/licenses/new", json=body, headers=headers)
    assert response.status_code == 200
    value = response.json()
    row = asyncio.run(env.DB.prepare("SELECT * FROM licenses WHERE token_hash = ?").bind(value["license"]["identifier"]).first())
    event = asyncio.run(env.DB.prepare("SELECT * FROM admin_operations WHERE request_id = ?").bind(body["request_id"]).first())
    assert value["key"] not in json.dumps([row, event])
    assert row["customer"] == body["customer"]


def test_unknown_license_does_not_create_an_audit_event(panel):
    client, env, headers = signed(panel)
    body = {"request_id": str(uuid4()), "days": 30}
    response = client.post("/api/licenses/" + "a" * 64 + "/extend", json=body, headers=headers)
    assert response.status_code == 404
    assert asyncio.run(env.DB.prepare("SELECT * FROM admin_operations WHERE request_id = ?").bind(body["request_id"]).first()) is None
