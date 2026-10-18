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
        # شبیه‌ساز روی loopback است؛ پراکسی سیستم مک نباید ترافیک محلی آزمون را بگیرد.
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.post(self.url, headers={"Authorization": self.token},
                json={"sql": self.sql, "params": self.params, "method": method})
            response.raise_for_status()
            return response.json()
    async def first(self):
        return await self.request("first")
    async def all(self):
        return await self.request("all")
    async def run(self):
        return await self.request("run")


class D1:
    def __init__(self, url, token):
        self.url, self.token = url, token
    def prepare(self, sql):
        return D1Statement(self.url, self.token, sql)
    async def batch(self, statements):
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.post(self.url, headers={"Authorization": self.token},
                json={"method": "batch", "statements": [{"sql": item.sql, "params": item.params} for item in statements]})
            response.raise_for_status()
            return response.json()


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
        for migration in sorted((ROOT / "gateway/migrations").glob("*.sql")):
            for statement in migration.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    asyncio.run(database.prepare(statement).all())
        yield database
    finally:
        process.terminate()
        process.wait(timeout=20)
