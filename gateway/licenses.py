"""لایسنس D1؛ فقط هش کلید و شمارنده نگه داشته می‌شود، نه متن مدل."""

import hashlib
import time
from datetime import datetime, timezone


ERRORS = {
    "license_invalid": (401, "کد لایسنس معتبر نیست؛ کد را بررسی کنید."),
    "license_revoked": (403, "این لایسنس غیرفعال شده است؛ با پشتیبانی تماس بگیرید."),
    "license_expired": (402, "اعتبار لایسنس تمام شده است؛ برای تمدید با پشتیبانی تماس بگیرید."),
    "quota_exceeded": (429, "سهمیهٔ روزانهٔ درخواست مدل تمام شده است؛ فردا دوباره تلاش کنید."),
}

RESERVE_SQL = """UPDATE licenses
    SET used = CASE WHEN usage_day = ? THEN used + 1 ELSE 1 END, usage_day = ?
    WHERE token_hash = ? AND active = 1 AND expires_at > ?
      AND (usage_day <> ? OR used < daily_limit)
    RETURNING customer, plan, expires_at, daily_limit, used, usage_day"""


def token_hash(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def plain(value):
    return value.to_py() if hasattr(value, "to_py") else value


def failure(row, now):
    if row is None:
        return "license_invalid"
    if not row["active"]:
        return "license_revoked"
    if row["expires_at"] <= now:
        return "license_expired"
    return None


class Licenses:
    def __init__(self, db):
        self.db = db

    async def read(self, key):
        return plain(await self.db.prepare("SELECT * FROM licenses WHERE token_hash = ?")
                     .bind(token_hash(key)).first())

    async def reserve(self, key, now=None):
        now = int(time.time()) if now is None else now
        day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        # بررسی اعتبار و افزایش سهمیه یک دستور است؛ درخواست هم‌زمان از سقف عبور نمی‌کند.
        row = plain(await self.db.prepare(RESERVE_SQL).bind(day, day, token_hash(key), now, day).first())
        if row is not None:
            return row, None
        current = await self.read(key)
        return None, failure(current, now) or "quota_exceeded"
