"""تنظیم اتصال مشترک سازمان؛ رمز فقط رمزگذاری‌شده ذخیره و هر بار دوباره بررسی می‌شود."""

import hashlib
import json
import secrets
import time

from cryptography import x509
from cryptography.fernet import Fernet, InvalidToken

from organization_portal import network
from organization_portal.errors import PortalError
from organization_portal.permissions import event_sql, membership, source_list


class Connections:
    def __init__(self, store, key, engine, local=False):
        self.store = store
        self.cipher = Fernet(key.encode())
        self.engine = engine
        self.local = local

    def _input(self, member, data):
        try:
            uri = network.connection_uri(data["db_type"], data["values"], data.get("advanced_uri", ""))
            hosts = source_list(member["allowed_hosts"])
            network.check_destination(uri, hosts, self.local)
            database = data["values"].get("database", "").strip()
            if not database or len(database) > 200:
                raise ValueError()
            ca = data.get("ca_pem", "").strip()
            if len(ca) > 64000:
                raise ValueError()
            if ca:
                x509.load_pem_x509_certificate(ca.encode())
            return {"db_type": data["db_type"], "uri": uri, "database": database,
                    "allowed_hosts": hosts, "ca_pem": ca}
        except (KeyError, TypeError, ValueError):
            raise PortalError("اطلاعات اتصال یا گواهی معتبر نیست.") from None

    def probe(self, user, org_id, data):
        member = membership(self.store, user, org_id, admin=True)
        job = self._input(member, data)
        return self.engine.run({**job, "mode": "probe"})

    def save(self, user, org_id, data):
        member = membership(self.store, user, org_id, admin=True)
        job = self._input(member, data)
        checked = self.engine.run({**job, "mode": "probe"})
        if not checked.get("ok"):
            return checked
        selected = source_list(data.get("sources", []))
        if not selected or not set(selected) <= set(checked["sources"]):
            raise PortalError("حداقل یک منبع موجود را انتخاب کنید.")
        documentation = data.get("documentation", "")
        if not isinstance(documentation, str) or len(documentation) > 100000:
            raise PortalError("توضیح داده‌ها بیش از اندازه بلند است.")
        uri_cipher = self.cipher.encrypt(job["uri"].encode()).decode()
        sql = """INSERT INTO connections(org_id,id,db_type,database_name,uri_cipher,ca_pem,allowed_sources,documentation,updated)
            VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(org_id) DO UPDATE SET db_type=excluded.db_type,
            database_name=excluded.database_name,uri_cipher=excluded.uri_cipher,ca_pem=excluded.ca_pem,
            allowed_sources=excluded.allowed_sources,documentation=excluded.documentation,
            revision=revision+1,updated=excluded.updated"""
        self.store.batch([(sql, (org_id, secrets.token_hex(16), job["db_type"], job["database"], uri_cipher,
            job["ca_pem"], json.dumps(selected), documentation, int(time.time()))),
            event_sql(org_id, user["id"], "connection_saved", org_id)])
        return {"ok": True, "message": "اتصال امن مشترک سازمان ذخیره شد."}

    def public(self, user, org_id):
        membership(self.store, user, org_id, admin=True)
        rows = self.store.query("""SELECT id,db_type,database_name,allowed_sources,documentation,revision
            FROM connections WHERE org_id=?""", org_id)
        return rows[0] if rows else None

    def authorized(self, user, org_id):
        member = membership(self.store, user, org_id)
        rows = self.store.query("SELECT * FROM connections WHERE org_id=?", org_id)
        if not rows:
            raise PortalError("مدیر سازمان هنوز اتصال دیتابیس را تنظیم نکرده است.", 409)
        connection = rows[0]
        permitted = source_list(connection["allowed_sources"])
        sources = permitted if member["role"] == "admin" else sorted(set(permitted) & set(source_list(member["allowed_sources"])))
        if not sources:
            raise PortalError("هنوز منبعی برای حساب شما مجاز نشده؛ با مدیر سازمان تماس بگیرید.", 403)
        try:
            uri = self.cipher.decrypt(connection["uri_cipher"].encode()).decode()
        except (InvalidToken, ValueError, UnicodeError):
            raise PortalError("راز اتصال قابل خواندن نیست؛ تنظیمات کلید سرور را بررسی کنید.", 503) from None
        job = {"db_type": connection["db_type"], "database": connection["database_name"], "uri": uri,
               "ca_pem": connection["ca_pem"], "documentation": connection["documentation"],
               "sources": sources, "allowed_hosts": source_list(member["allowed_hosts"])}
        job["connection_key"] = hashlib.sha256(json.dumps([connection["id"], network.identity(uri, job["database"])]).encode()).hexdigest()
        scope = [job["connection_key"], sources]
        key = hashlib.sha256(json.dumps(scope).encode()).hexdigest()
        return member, job, key
