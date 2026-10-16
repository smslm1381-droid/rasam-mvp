"""آماده‌سازی اتصال راهنما؛ اطلاعات حساس فقط در vault می‌ماند."""

from dataclasses import asdict
import hashlib
import threading

from rasam import config, vault
from rasam.databases import registry


def invalid_input():
    return {"ok": False, "category": "invalid", "message": "اطلاعات اتصال معتبر نیست؛ مقدارهای فرم را بررسی کنید."}


def database_forms():
    return [{"type": name, "fields": agent.connection_fields()}
            for name, agent in registry.AGENTS.items()]


class ConnectionSetup:
    def __init__(self):
        home_hash = hashlib.sha256(str(config.DATA_HOME).encode()).hexdigest()[:20].upper()
        self.secret_name = "PENDING_DB_" + home_hash
        self.pending = None
        self.lock = threading.RLock()

    def test(self, db_type, values, advanced_uri=""):
        with self.lock:
            return self._test(db_type, values, advanced_uri)

    def _test(self, db_type, values, advanced_uri):
        self.pending = None
        agent = registry.AGENTS.get(db_type)
        if agent is None:
            return invalid_input()
        try:
            uri = advanced_uri.strip() or agent.build_connection_uri(values)
            database = values.get("database", "").strip()
            result = agent.test_connection(uri, database)
            if not result.ok:
                return asdict(result)
            saved = vault.write_secret(self.secret_name, uri)
            if not saved.ok:
                return {"ok": False, "category": "vault", "message": saved.error}
            self.pending = {"db_type": db_type, "database": database,
                            "connection_env": self.secret_name}
            return {**asdict(result), "message": "اتصال برقرار شد؛ اطلاعات در انبار امن رمز ذخیره شد."}
        except Exception:
            return invalid_input()
