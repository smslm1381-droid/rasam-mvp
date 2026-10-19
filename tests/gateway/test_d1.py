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
        assert names == {"token_hash", "customer", "plan", "expires_at", "daily_limit", "active", "usage_day", "used", "model", "product_id"}
    asyncio.run(run())
