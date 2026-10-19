"""نشست‌های ورود در ذخیره‌ساز مرکزی‌اند و در همهٔ دستگاه‌ها یک هویت را می‌شناسند."""

import secrets
import time

from organization_portal import passwords
from organization_portal.errors import PortalError


class Accounts:
    def __init__(self, store):
        self.store = store

    def create(self, email, name, password, platform_admin=False):
        identity = secrets.token_hex(16)
        self.store.query("INSERT INTO users(id,email,name,password_hash,platform_admin,created) VALUES (?,?,?,?,?,?)",
                         identity, passwords.email(email), name.strip()[:100], passwords.encode(password),
                         int(platform_admin), int(time.time()))
        return identity

    def _limit(self, email, address):
        now = int(time.time())
        sql = """INSERT INTO login_limits(bucket,window,attempts) VALUES (?,?,1)
            ON CONFLICT(bucket) DO UPDATE SET window=excluded.window,
            attempts=CASE WHEN window=excluded.window THEN attempts+1 ELSE 1 END
            WHERE window<>excluded.window OR attempts<5 RETURNING attempts"""
        for name in ("email:" + email, "address:" + address):
            if not self.store.query(sql, passwords.digest(name), now // 300):
                raise PortalError("تلاش‌های ورود زیاد است؛ پنج دقیقه بعد دوباره تلاش کنید.", 429)

    def login(self, email, password, address):
        email = passwords.email(email)
        self._limit(email, address)
        rows = self.store.query("SELECT * FROM users WHERE email=? AND active=1", email)
        dummy = f"pbkdf2_sha256${passwords.ITERATIONS}$" + "0" * 32 + "$" + "0" * 64
        valid = passwords.verify(password, rows[0]["password_hash"] if rows else dummy)
        if not valid or not rows:
            raise PortalError("ایمیل یا رمز درست نیست.", 401)
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        self.store.batch([("DELETE FROM sessions WHERE expires<=?", (now,)),
            ("INSERT INTO sessions(token_hash,user_id,expires) VALUES (?,?,?)",
             (passwords.digest(token), rows[0]["id"], now + 8 * 3600))])
        return token

    def current(self, token):
        if not token or not 40 <= len(token) <= 100:
            return None
        rows = self.store.query("""SELECT u.id,u.email,u.name,u.platform_admin FROM sessions s
            JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1""",
            passwords.digest(token), int(time.time()))
        return rows[0] if rows else None

    def logout(self, token):
        self.store.query("DELETE FROM sessions WHERE token_hash=?", passwords.digest(token or ""))

    def change_password(self, user, old, new):
        row = self.store.query("SELECT password_hash FROM users WHERE id=?", user["id"])[0]
        if not passwords.verify(old, row["password_hash"]):
            raise PortalError("رمز فعلی درست نیست.", 403)
        encoded = passwords.encode(new)
        self.store.batch([("UPDATE users SET password_hash=? WHERE id=?", (encoded, user["id"])),
                          ("DELETE FROM sessions WHERE user_id=?", (user["id"],))])
