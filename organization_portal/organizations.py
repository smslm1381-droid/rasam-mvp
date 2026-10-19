"""مدیر سازمان فقط اعضای همان سازمان را تغییر می‌دهد و راز یا محتوای گفتگو نمی‌گیرد."""

import json
import secrets
import time

from organization_portal import invitations, passwords, usage
from organization_portal.errors import PortalError
from organization_portal.permissions import event_sql, membership, platform_admin, source_list


def create(store, user, name, manager_email, hosts, limit):
    platform_admin(user)
    manager_email = passwords.email(manager_email)
    if not name.strip() or len(name) > 100 or not 1 <= limit <= 100000:
        raise PortalError("نام سازمان یا سهمیه معتبر نیست.")
    hosts = source_list(hosts)
    if any(any(char in host for char in "/@?# ") for host in hosts):
        raise PortalError("مقصدهای مجاز باید نام میزبان یا IP باشند.")
    identity = secrets.token_hex(16)
    store.batch([("INSERT INTO organizations(id,name,daily_limit,allowed_hosts,created) VALUES (?,?,?,?,?)",
        (identity, name.strip(), limit, json.dumps(hosts), int(time.time()))),
        event_sql(identity, user["id"], "organization_created", identity)])
    invitation = invitations.issue(store, identity, manager_email, "admin", limit, [], user["id"])
    return {"id": identity, "name": name.strip(), "invitation": invitation}


def members(store, user, org_id):
    membership(store, user, org_id, admin=True)
    return store.query("""SELECT m.id,m.user_id,u.email,u.name,m.role,m.active,m.daily_limit,m.allowed_sources,
        COALESCE(d.used,0) AS used,COALESCE(d.reserved,0) AS reserved
        FROM memberships m JOIN users u ON u.id=m.user_id
        LEFT JOIN daily_usage d ON d.bucket='user:' || m.org_id || ':' || m.user_id AND d.day=?
        WHERE m.org_id=? ORDER BY u.name""", usage.day(), org_id)


def invite(store, user, org_id, email, role, limit, sources):
    member = membership(store, user, org_id, admin=True)
    selected = source_list(sources)
    allowed = store.query("SELECT allowed_sources FROM connections WHERE org_id=?", org_id)
    if selected and (not allowed or not set(selected) <= set(source_list(allowed[0]["allowed_sources"]))):
        raise PortalError("منابع دعوت باید از منابع مجاز اتصال سازمان باشند.")
    if limit > member["org_limit"]:
        raise PortalError("سهمیهٔ عضو از سهمیهٔ سازمان بیشتر است.")
    return invitations.issue(store, org_id, email, role, limit, selected, user["id"])


def update_member(store, user, org_id, member_id, active, limit, sources):
    current = membership(store, user, org_id, admin=True)
    rows = store.query("SELECT * FROM memberships WHERE id=? AND org_id=?", member_id, org_id)
    if not rows:
        raise PortalError("عضو پیدا نشد.", 404)
    if rows[0]["user_id"] == user["id"] and not active:
        raise PortalError("حساب مدیریتی خود را نمی‌توانید غیرفعال کنید.")
    if not 1 <= limit <= current["org_limit"]:
        raise PortalError("سهمیهٔ عضو باید بین یک و سهمیهٔ سازمان باشد.")
    selected = source_list(sources)
    allowed = store.query("SELECT allowed_sources FROM connections WHERE org_id=?", org_id)
    if selected and (not allowed or not set(selected) <= set(source_list(allowed[0]["allowed_sources"]))):
        raise PortalError("منابع انتخابی خارج از دسترسی سازمان هستند.")
    store.batch([("UPDATE memberships SET active=?,daily_limit=?,allowed_sources=? WHERE id=? AND org_id=?",
        (int(active), limit, json.dumps(selected), member_id, org_id)),
        event_sql(org_id, user["id"], "membership_updated", member_id)])
    return {"ok": True}


def configure(store, user, org_id, active, limit, hosts, manager_chat_access):
    platform_admin(user)
    hosts = source_list(hosts)
    if not 1 <= limit <= 100000 or any(any(char in host for char in "/@?# ") for host in hosts):
        raise PortalError("سهمیه یا مقصدهای مجاز معتبر نیستند.")
    changed = store.batch([("""UPDATE organizations SET active=?,daily_limit=?,allowed_hosts=?,manager_chat_access=?
        WHERE id=? RETURNING id""", (int(active), limit, json.dumps(hosts), int(manager_chat_access), org_id)),
        event_sql(org_id, user["id"], "organization_policy_updated", org_id)])
    if not changed[0]["results"]:
        raise PortalError("سازمان پیدا نشد.", 404)
    return {"ok": True}
