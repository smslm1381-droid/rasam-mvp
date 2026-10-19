"""سهمیه با رزرو اتمی کنترل می‌شود؛ درخواست هم‌زمان یا قطع فرایند شمارنده را دور نمی‌زند."""

from datetime import datetime, timezone
import json
import secrets
import time

from organization_portal.errors import PortalError


def day():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def buckets(org_id, user_id):
    return ["org:" + org_id, "user:" + org_id + ":" + user_id]


def summary(store, org_id, user_id):
    names = buckets(org_id, user_id)
    rows = store.query("SELECT bucket,used,reserved FROM daily_usage WHERE day=? AND bucket IN (?,?)", day(), *names)
    values = {row["bucket"]: {"used": row["used"], "reserved": row["reserved"]} for row in rows}
    return {"day": day(), "organization": values.get(names[0], {"used": 0, "reserved": 0}),
            "member": values.get(names[1], {"used": 0, "reserved": 0})}


def reserve(store, member, chat_id, turn_id, question):
    org_id, user_id = member["org_id"], member["user_id"]
    names = buckets(org_id, user_id)
    today, now, identity = day(), int(time.time()), secrets.token_hex(16)
    statements = [("INSERT INTO daily_usage(bucket,day) VALUES (?,?) ON CONFLICT DO NOTHING", (name, today)) for name in names]
    sql = """INSERT INTO reservations(id,org_id,user_id,turn_id,day,expires,state)
        SELECT ?,?,?,?,?,?,'pending' WHERE EXISTS(SELECT 1 FROM chats WHERE id=? AND busy_turn_id IS NULL)
        AND EXISTS(SELECT 1 FROM daily_usage WHERE bucket=? AND day=? AND used+reserved<?)
        AND EXISTS(SELECT 1 FROM daily_usage WHERE bucket=? AND day=? AND used+reserved<?) RETURNING id"""
    statements.append((sql, (identity, org_id, user_id, turn_id, today, now + 300, chat_id,
                            names[0], today, member["org_limit"], names[1], today, member["daily_limit"])))
    gate = "EXISTS(SELECT 1 FROM reservations WHERE id=? AND state='pending')"
    statements.extend([
        ("UPDATE daily_usage SET reserved=reserved+1 WHERE day=? AND bucket IN (?,?) AND " + gate,
         (today, *names, identity)),
        ("UPDATE chats SET busy_turn_id=? WHERE id=? AND " + gate, (turn_id, chat_id, identity)),
        ("INSERT INTO turns(id,chat_id,question,status,created) SELECT ?,?,?,'pending',? WHERE " + gate,
         (turn_id, chat_id, question, now, identity))])
    results = store.batch(statements)
    if not results[2]["results"]:
        row = store.query("SELECT busy_turn_id FROM chats WHERE id=?", chat_id)
        if row and row[0]["busy_turn_id"]:
            raise PortalError("پاسخ قبلی این گفتگو هنوز آماده نشده است؛ کمی صبر کنید.", 409)
        raise PortalError("سهمیهٔ روزانهٔ عضو یا سازمان تمام شده است.", 429)
    return identity


def finish(store, identity, answer, success):
    rows = store.query("SELECT * FROM reservations WHERE id=?", identity)
    if not rows:
        return
    row = rows[0]
    names = buckets(row["org_id"], row["user_id"])
    gate = "EXISTS(SELECT 1 FROM reservations WHERE id=? AND state='pending')"
    encoded = json.dumps(answer, ensure_ascii=False, default=str, allow_nan=False)
    if len(encoded.encode()) > 900000:
        encoded = json.dumps({"question": answer.get("question", ""), "error": "نتیجه برای ذخیرهٔ گفتگو بیش از حد بزرگ است."}, ensure_ascii=False)
        success = False
    state = "used" if success else "released"
    store.batch([
        ("UPDATE daily_usage SET reserved=reserved-1,used=used+? WHERE day=? AND bucket IN (?,?) AND " + gate,
         (int(success), row["day"], *names, identity)),
        ("UPDATE reservations SET state=? WHERE id=? AND state='pending'", (state, identity)),
        ("UPDATE turns SET answer=?,status=? WHERE id=? AND status='pending'",
         (encoded, "complete" if success else "failed", row["turn_id"])),
        ("UPDATE chats SET busy_turn_id=NULL,updated=? WHERE busy_turn_id=?", (int(time.time()), row["turn_id"]))])
    return json.loads(encoded)


def recover(store):
    rows = store.query("SELECT id,turn_id FROM reservations WHERE state='pending' AND expires<? LIMIT 100",
                       int(time.time()))
    for row in rows:
        turn = store.query("SELECT question FROM turns WHERE id=?", row["turn_id"])
        question = turn[0]["question"] if turn else ""
        finish(store, row["id"], {"question": question, "error": "اجرای قبلی قطع شد؛ سهمیهٔ آن برگردانده شد."}, False)


def rate_limit(store, org_id, user_id):
    sql = """INSERT INTO login_limits(bucket,window,attempts) VALUES (?,?,1)
        ON CONFLICT(bucket) DO UPDATE SET window=excluded.window,
        attempts=CASE WHEN window=excluded.window THEN attempts+1 ELSE 1 END
        WHERE window<>excluded.window OR attempts<? RETURNING attempts"""
    now = int(time.time())
    for bucket, maximum in [("ask-user:" + user_id, 10), ("ask-org:" + org_id, 60)]:
        if not store.query(sql, bucket, now // 60, maximum):
            raise PortalError("درخواست‌ها زیاد است؛ یک دقیقه بعد دوباره تلاش کنید.", 429)
