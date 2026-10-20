"""دعوت فقط به سازمان تعیین‌شده راه می‌دهد؛ حساب موجود با دعوت تصاحب یا بازنویسی نمی‌شود."""

import json
import secrets
import time

from organization_portal import passwords
from organization_portal.errors import PortalError
from organization_portal.permissions import event_sql


def issue(store, org_id, email, role, limit, sources, actor_id):
    if role not in {"admin", "member"} or not 1 <= limit <= 100000:
        raise PortalError("نقش یا سهمیهٔ دعوت معتبر نیست.")
    token = secrets.token_urlsafe(32)
    identity = secrets.token_hex(16)
    expires = int(time.time()) + 7 * 86400
    store.batch([("INSERT INTO invitations(id,token_hash,org_id,email,role,daily_limit,allowed_sources,expires) VALUES (?,?,?,?,?,?,?,?)",
        (identity, passwords.digest(token), org_id, passwords.email(email), role, limit, json.dumps(sources), expires)),
        event_sql(org_id, actor_id, "invitation_created", identity)])
    return {"id": identity, "token": token, "expires": expires,
            "message": "دعوت آماده است؛ آن را خصوصی به صاحب ایمیل برسانید. ارسال ایمیل خودکار فعال نیست."}


def details(store, token):
    rows = store.query("""SELECT i.*,o.name AS org_name FROM invitations i JOIN organizations o ON o.id=i.org_id
        WHERE token_hash=? AND claim_id IS NULL AND expires>? AND o.active=1""", passwords.digest(token), int(time.time()))
    if not rows:
        raise PortalError("دعوت معتبر نیست یا زمان آن تمام شده است.", 404)
    row = rows[0]
    existing = bool(store.query("SELECT id FROM users WHERE email=?", row["email"]))
    return row, existing


def accept(store, token, name, password, current):
    row, existing = details(store, token)
    if existing and (not current or current["email"] != row["email"]):
        raise PortalError("این ایمیل حساب دارد؛ ابتدا با همان حساب وارد شوید و دعوت را بپذیرید.", 401)
    if not existing and (not name.strip() or len(name) > 100):
        raise PortalError("نام را بین ۱ تا ۱۰۰ کاراکتر وارد کنید.")
    encoded = None if existing else passwords.encode(password)
    user_id = current["id"] if existing else secrets.token_hex(16)
    claim = secrets.token_hex(16)
    now = int(time.time())
    gate = "EXISTS(SELECT 1 FROM invitations WHERE id=? AND claim_id=?)"
    statements = [("UPDATE invitations SET claim_id=? WHERE id=? AND claim_id IS NULL AND expires>? RETURNING id",
                   (claim, row["id"], now))]
    if not existing:
        statements.append(("INSERT INTO users(id,email,name,password_hash,created) SELECT ?,?,?,?,? WHERE " + gate,
                           (user_id, row["email"], name.strip(), encoded, now, row["id"], claim)))
    statements.append(("INSERT INTO memberships(id,org_id,user_id,role,daily_limit,allowed_sources) SELECT ?,?,?,?,?,? WHERE "
        + gate + " ON CONFLICT(org_id,user_id) DO NOTHING",
        (secrets.token_hex(16), row["org_id"], user_id, row["role"], row["daily_limit"], row["allowed_sources"], row["id"], claim)))
    result = store.batch(statements)
    if not result[0]["results"]:
        raise PortalError("دعوت قبلاً استفاده شده است.", 409)
    return {"ok": True, "message": "عضویت فعال شد؛ با حساب خود وارد شوید."}
