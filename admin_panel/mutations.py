"""تغییر لایسنس و ثبت درخواست یک تراکنش D1 است تا تکرار درخواست دوباره اثر نکند."""

import hashlib
import json
import time
from uuid import UUID

from gateway import license_commands
from gateway.licenses import plain
from admin_panel.store import public_row

AUDIT_SQL = """INSERT INTO admin_operations(request_id, actor, fingerprint, action, license_hash, created_at)
    SELECT ?, ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM licenses WHERE token_hash = ?)"""


def prepared(action, body, identifier):
    fields = {"new": {"customer", "plan", "daily_limit"}, "extend": {"days"},
              "revoke": set(), "quota": {"daily_limit"}}
    expected = fields.get(action, set()) | {"request_id"}
    if action == "new" and ("model" in body or "product_id" in body):
        expected |= {"model", "product_id"}
    if action not in fields or set(body) != expected:
        raise ValueError("فیلدهای درخواست کامل یا معتبر نیستند.")
    request_id = body.get("request_id")
    if not isinstance(request_id, str) or str(UUID(request_id)) != request_id:
        raise ValueError("شناسهٔ درخواست معتبر نیست؛ صفحه را دوباره باز کنید.")
    key = None
    if action == "new":
        key, identifier, _, sql = license_commands.issue(body["customer"], body["plan"], body["daily_limit"],
                                                      model=body.get("model"), product_id=body.get("product_id"))
        sql = sql.rstrip(";") + " RETURNING token_hash;"
    elif action == "quota":
        sql = license_commands.quota(identifier, body["daily_limit"])
    else:
        sql = license_commands.change(identifier, body.get("days") if action == "extend" else None)
    fingerprint = hashlib.sha256(json.dumps([action, identifier if action != "new" else None, body],
                                           sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return request_id, fingerprint, key, identifier, sql


async def previous(db, request_id):
    return plain(await db.prepare("SELECT * FROM admin_operations WHERE request_id = ?").bind(request_id).first())


async def result_for(db, identifier, key, replayed):
    row = plain(await db.prepare("SELECT * FROM licenses WHERE token_hash = ?").bind(identifier).first())
    if row is None:
        return {"ok": False, "message": "لایسنس موردنظر پیدا نشد."}, 404
    return {"ok": True, "license": public_row(row, int(time.time())), "key": key, "replayed": replayed}, 200


async def replay(db, row, actor, fingerprint):
    if row["actor"] != actor or row["fingerprint"] != fingerprint:
        return {"ok": False, "message": "شناسهٔ این درخواست قبلاً برای عملیات دیگری استفاده شده است."}, 409
    # کد خام قبلی را ذخیره نمی‌کنیم؛ تکرار صدور فقط نتیجهٔ ثبت‌شده را نشان می‌دهد.
    return await result_for(db, row["license_hash"], None, True)


async def perform(db, actor, action, body, identifier=None):
    try:
        request_id, fingerprint, key, identifier, sql = prepared(action, body, identifier)
    except (ValueError, TypeError):
        return {"ok": False, "message": "اطلاعات عملیات معتبر نیست؛ نام، پلن و عددها را بررسی کنید."}, 400
    existing = await previous(db, request_id)
    if existing:
        return await replay(db, existing, actor, fingerprint)
    statements = [db.prepare(sql), db.prepare(AUDIT_SQL).bind(request_id, actor, fingerprint,
                  action, identifier, int(time.time()), identifier)]
    try:
        results = plain(await db.batch(statements))
    except Exception:
        existing = await previous(db, request_id)
        if existing:
            return await replay(db, existing, actor, fingerprint)
        raise
    if not results[0].get("results"):
        return {"ok": False, "message": "لایسنس موردنظر پیدا نشد."}, 404
    return await result_for(db, identifier, key, False)


async def recent(db):
    result = plain(await db.prepare("""SELECT o.action, o.actor, o.created_at, l.customer
        FROM admin_operations o LEFT JOIN licenses l ON l.token_hash = o.license_hash
        ORDER BY o.created_at DESC, o.request_id DESC LIMIT 20""").all())
    return {"events": result.get("results", [])}
