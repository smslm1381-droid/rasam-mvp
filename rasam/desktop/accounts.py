"""یک حساب محلی؛ رمز خام ذخیره نمی‌شود و این حساب جای حساب سازمانی نیست."""

import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path


@dataclass
class Result:
    ok: bool
    reason: str = ""


class LocalAccount:
    def __init__(self, path, enabled=True):
        self.path = Path(path)
        self.enabled = enabled
        self.lock = threading.RLock()
        self.sessions = {}

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        self.path.chmod(0o600)
        db.execute("CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, salt BLOB NOT NULL, digest BLOB NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, retry_at INTEGER NOT NULL DEFAULT 0)")
        try:
            with db:
                yield db
        finally:
            db.close()

    def state(self):
        if not self.enabled:
            return {"required": False, "registered": False}
        try:
            with self.lock, self._connect() as db:
                row = db.execute("SELECT username FROM account WHERE id=1").fetchone()
            return {"required": True, "registered": row is not None}
        except (OSError, sqlite3.Error):
            return {"required": True, "registered": True, "error": "حساب محلی قابل خواندن نیست؛ دوباره تلاش کنید."}

    @staticmethod
    def _digest(password, salt):
        return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)

    def register(self, username, password):
        username = username.strip()
        if not 3 <= len(username) <= 80 or not 8 <= len(password) <= 128:
            return Result(False, "نام کاربری ۳ تا ۸۰ و رمز عبور ۸ تا ۱۲۸ کاراکتر باشد.")
        try:
            salt = secrets.token_bytes(16)
            digest = self._digest(password, salt)
            with self.lock, self._connect() as db:
                db.execute("INSERT INTO account(id,username,salt,digest) VALUES (1,?,?,?)", (username, salt, digest))
            return Result(True)
        except sqlite3.IntegrityError:
            return Result(False, "حساب قبلاً ساخته شده است؛ وارد شوید.")
        except (OSError, sqlite3.Error, ValueError):
            return Result(False, "ذخیرهٔ حساب محلی انجام نشد؛ دوباره تلاش کنید.")

    def login(self, username, password):
        try:
            with self.lock, self._connect() as db:
                row = db.execute("SELECT username,salt,digest,attempts,retry_at FROM account WHERE id=1").fetchone()
                if row is None:
                    return Result(False, "ابتدا لایسنس را فعال و حساب را ایجاد کنید.")
                if row[4] > time.time():
                    return Result(False, "تلاش‌های ورود زیاد است؛ پنج دقیقه بعد دوباره تلاش کنید.")
                valid = hmac.compare_digest(self._digest(password, row[1]), row[2])
                valid = hmac.compare_digest(username.strip().encode(), row[0].encode()) and valid
                attempts = 0 if valid else (row[3] + 1 if row[4] == 0 else 1)
                retry = int(time.time()) + 300 if attempts >= 5 else 0
                db.execute("UPDATE account SET attempts=?,retry_at=? WHERE id=1", (attempts, retry))
            return Result(valid, "" if valid else "نام کاربری یا رمز عبور درست نیست.")
        except (OSError, sqlite3.Error, ValueError):
            return Result(False, "بررسی حساب محلی انجام نشد؛ دوباره تلاش کنید.")

    def issue_session(self):
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.lock:
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            self.sessions[hashlib.sha256(token.encode()).digest()] = now + 8 * 3600
        return token

    def authenticated(self, token):
        if not self.enabled:
            return True
        if not isinstance(token, str) or not 40 <= len(token) <= 100:
            return False
        with self.lock:
            return self.sessions.get(hashlib.sha256(token.encode()).digest(), 0) > time.time()

    def logout(self, token):
        with self.lock:
            self.sessions.pop(hashlib.sha256(token.encode()).digest(), None)
