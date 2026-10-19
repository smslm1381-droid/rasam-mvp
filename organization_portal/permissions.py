"""شناسهٔ سازمان از نشست و عضویت معتبر می‌آید؛ انتخاب مرورگر مجوز ایجاد نمی‌کند."""

import json
import time
import secrets

from organization_portal.errors import PortalError


def platform_admin(user):
    if not user or not user["platform_admin"]:
        raise PortalError("این عملیات مخصوص مدیر کل رصام است.", 403)


def membership(store, user, org_id, admin=False):
    rows = store.query("""SELECT m.*,o.name AS org_name,o.daily_limit AS org_limit,o.allowed_hosts,o.manager_chat_access
        FROM memberships m JOIN organizations o ON o.id=m.org_id
        WHERE m.org_id=? AND m.user_id=? AND m.active=1 AND o.active=1""", org_id, user["id"])
    if not rows or admin and rows[0]["role"] != "admin":
        raise PortalError("اجازهٔ دسترسی به این سازمان یا عملیات را ندارید.", 403)
    return rows[0]


def organizations(store, user):
    return store.query("""SELECT o.id,o.name,m.role,o.manager_chat_access FROM organizations o
        JOIN memberships m ON m.org_id=o.id WHERE m.user_id=? AND m.active=1 AND o.active=1
        ORDER BY o.name""", user["id"])


def source_list(value):
    try:
        result = json.loads(value) if isinstance(value, str) else value
        if not isinstance(result, list) or len(result) > 200 or any(
            not isinstance(item, str) or not item or len(item) > 200 for item in result):
            raise ValueError()
        return sorted(set(result))
    except (TypeError, ValueError):
        raise PortalError("فهرست منابع معتبر نیست.") from None


def event_sql(org_id, user_id, action, subject_id):
    return ("INSERT INTO audit_events(id,org_id,actor_id,action,subject_id,created) VALUES (?,?,?,?,?,?)",
            (secrets.token_hex(16), org_id, user_id, action, subject_id, int(time.time())))
