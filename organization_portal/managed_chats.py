"""دسترسی نظارتی فقط با قابلیت اعطاشدهٔ ادمین کل و در محدودهٔ اتصال همان سازمان است."""

import json

from organization_portal.errors import PortalError
from organization_portal.permissions import event_sql, membership


def permitted(store, connections, user, org_id):
    member = membership(store, user, org_id, admin=True)
    if not member["manager_chat_access"]:
        raise PortalError("امکان مشاهدهٔ گفتگوهای اعضا برای این سازمان فعال نشده است.", 403)
    _, job, _ = connections.authorized(user, org_id)
    return job


def visible(chat, job):
    return chat["connection_key"] == job["connection_key"] and set(json.loads(chat["source_scope"])) <= set(job["sources"])


def listing(store, connections, user, org_id):
    job = permitted(store, connections, user, org_id)
    rows = store.query("""SELECT c.*,u.name,u.email FROM chats c JOIN users u ON u.id=c.user_id
        WHERE c.org_id=? ORDER BY c.updated DESC,c.id LIMIT 200""", org_id)
    return [{key: row[key] for key in ("id", "title", "updated", "name", "email")}
            for row in rows if visible(row, job)]


def read(store, connections, user, org_id, chat_id):
    job = permitted(store, connections, user, org_id)
    rows = store.query("SELECT * FROM chats WHERE id=? AND org_id=?", chat_id, org_id)
    if not rows or not visible(rows[0], job):
        raise PortalError("گفتگو در دسترسی فعلی سازمان پیدا نشد.", 404)
    turns = store.query("SELECT id,question,answer,status,created FROM turns WHERE chat_id=? ORDER BY created,rowid", chat_id)
    store.batch([event_sql(org_id, user["id"], "member_chat_viewed", chat_id)])
    return {"id": chat_id, "title": rows[0]["title"], "read_only": True,
            "turns": [{**turn, "answer": json.loads(turn["answer"]) if turn["answer"] else None} for turn in turns]}
