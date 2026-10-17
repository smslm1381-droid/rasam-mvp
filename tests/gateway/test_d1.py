"""رفتار واقعی D1 با Miniflare؛ هیچ backend SQLite پایتونی در آزمون نیست."""

import asyncio
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from uuid import uuid4

import httpx
import pytest
from gateway import admin, licenses

ROOT = Path(__file__).resolve().parents[2]


class D1Statement:
    def __init__(self, url, token, sql, params=()):
        self.url, self.token, self.sql, self.params = url, token, sql, params
    def bind(self, *params):
        return D1Statement(self.url, self.token, self.sql, params)
    async def request(self, method):
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.url, headers={"Authorization": self.token},
                json={"sql": self.sql, "params": self.params, "method": method})
            response.raise_for_status()
            return response.json()
    async def first(self):
        return await self.request("first")
    async def all(self):
        return await self.request("all")


class D1:
    def __init__(self, url, token):
        self.url, self.token = url, token
    def prepare(self, sql):
        return D1Statement(self.url, self.token, sql)


@pytest.fixture(scope="module")
def d1():
    node = shutil.which("node")
    if node is None:
        found = list((ROOT / ".venv" / "tooling").glob("node-*-win-x64/node.exe"))
        node = str(found[0]) if found else None
    if node is None or not (ROOT / "gateway/node_modules/miniflare").exists():
        pytest.skip("آزمون واقعی D1 به Node و npm ci در gateway نیاز دارد.")
    token = secrets.token_urlsafe(32)
    process = subprocess.Popen([node, str(Path(__file__).with_name("d1_server.mjs"))], cwd=ROOT,
        env={**os.environ, "RASAM_TEST_TOKEN": token}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8")
    try:
        line = process.stdout.readline()
        if not line:
            pytest.fail("شبیه‌ساز D1 بالا نیامد؛ بسته‌های gateway را دوباره نصب کنید.")
        port = json.loads(line)["port"]
        database = D1(f"http://127.0.0.1:{port}", token)
        schema = (ROOT / "gateway/migrations/0001_licenses.sql").read_text(encoding="utf-8")
        asyncio.run(database.prepare(schema).all())
        yield database
    finally:
        process.terminate()
        process.wait(timeout=20)


def test_parallel_reservations_never_exceed_the_daily_limit_and_reset_at_utc_day(d1):
    async def run():
        key, identifier, expires, sql = admin.issue("race-" + uuid4().hex, "monthly", 3, now=1700000000)
        await d1.prepare(sql).all()
        service = licenses.Licenses(d1)
        outcomes = await asyncio.gather(*(service.reserve(key, now=1700000000) for _ in range(12)))
        assert sum(reason is None for row, reason in outcomes) == 3
        assert sum(reason == "quota_exceeded" for row, reason in outcomes) == 9
        row = await service.read(key)
        assert row["used"] == 3
        result, reason = await service.reserve(key, now=1700086400)
        assert reason is None and result["used"] == 1
    asyncio.run(run())


def test_expired_revoked_unknown_keys_and_admin_renewal_on_real_d1(d1):
    async def run():
        service = licenses.Licenses(d1)
        assert (await service.reserve("unknown", now=1700000000))[1] == "license_invalid"
        key, identifier, expires, sql = admin.issue("status", "monthly", now=1700000000)
        await d1.prepare(sql).all()
        assert (await service.reserve(key, now=expires))[1] == "license_expired"
        await d1.prepare(admin.change(identifier)).all()
        assert (await service.reserve(key, now=1700000000))[1] == "license_revoked"
        await d1.prepare(admin.change(identifier, days=30, now=expires)).all()
        assert (await service.reserve(key, now=expires))[1] is None
    asyncio.run(run())


def test_d1_stores_no_raw_license_question_or_model_result(d1):
    async def run():
        key, identifier, expires, sql = admin.issue("a'); DROP TABLE licenses; --", "yearly", now=1700000000)
        await d1.prepare(sql).all()
        row = await licenses.Licenses(d1).read(key)
        assert row["customer"] == "a'); DROP TABLE licenses; --"
        assert key not in json.dumps(row)
        columns = await d1.prepare("PRAGMA table_info(licenses)").all()
        names = {item["name"] for item in columns["results"]}
        assert names == {"token_hash", "customer", "plan", "expires_at", "daily_limit", "active", "usage_day", "used"}
    asyncio.run(run())
