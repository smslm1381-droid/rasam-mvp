"""سناریوهای چندسازمانی فقط با پاسخ‌گوی ساختگی؛ هیچ کلید یا دیتابیس واقعی خوانده نمی‌شود."""

import json
import secrets

from cryptography.fernet import Fernet
import pytest

from organization_portal.chats import Chats
from organization_portal.connections import Connections
from organization_portal.store import LocalStore


class FakeEngine:
    def __init__(self):
        self.calls = []
        self.failure = False
        self.complete = True
        self.on_answer = None

    def run(self, job):
        self.calls.append(job)
        if job["mode"] == "probe":
            return {"ok": True, "sources": ["readings", "private"], "message": "TEST"}
        if self.on_answer:
            self.on_answer()
        if self.failure:
            return {"ok": False, "message": "خطای آزمایشی"}
        return {"ok": True, "valid": True, "complete": self.complete,
                "answer": {"question": job["question"], "message": "پاسخ ساختگی تست", "error": None}}


@pytest.fixture
def workspace(tmp_path):
    store = LocalStore(tmp_path / "organizations.sqlite3")
    key = Fernet.generate_key().decode()
    engine = FakeEngine()
    users = {}
    for name in ["admin", "member", "other", "outside"]:
        user = {"id": secrets.token_hex(16), "email": name + "@example.invalid", "name": name, "platform_admin": 0}
        store.query("INSERT INTO users(id,email,name,password_hash,created) VALUES (?,?,?,?,0)",
                    user["id"], user["email"], name, "unused-test-digest")
        users[name] = user
    for org in ["one", "two"]:
        store.query("INSERT INTO organizations(id,name,daily_limit,allowed_hosts,created) VALUES (?,?,100,?,0)",
                    org, org, json.dumps(["127.0.0.1"]))
    for name in ["admin", "member", "other", "outside"]:
        org = "two" if name == "outside" else "one"
        role = "admin" if name in {"admin", "outside"} else "member"
        store.query("INSERT INTO memberships(id,org_id,user_id,role,daily_limit,allowed_sources) VALUES (?,?,?,?,10,?)",
                    name, org, users[name]["id"], role, json.dumps(["readings"]))
    connections = Connections(store, key, engine, local=True)
    values = {"host": "127.0.0.1", "username": "reader", "password": "private-test-db-password", "database": "data"}
    data = {"db_type": "mysql", "values": values, "sources": ["readings", "private"]}
    assert connections.save(users["admin"], "one", data)["ok"]
    assert connections.save(users["outside"], "two", data)["ok"]
    return {"store": store, "key": key, "users": users, "engine": engine,
            "connections": connections, "data": data, "chats": Chats(store, connections)}
