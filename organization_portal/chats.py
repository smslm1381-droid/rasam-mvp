"""گفتگو متعلق به کاربر و دسترسی فعلی اوست؛ URL یا لایسنس مشترک مالکیت نمی‌سازد."""

import json
import re
import secrets
import time

from organization_portal import usage
from organization_portal.errors import PortalError

REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{32,64}")


class Chats:
    def __init__(self, store, connections, quota_policy="complete_answer"):
        self.store = store
        self.connections = connections
        self.quota_policy = quota_policy

    def listing(self, user, org_id):
        _, _, key = self.connections.authorized(user, org_id)
        return self.store.query("""SELECT id,title,created,updated,busy_turn_id FROM chats
            WHERE org_id=? AND user_id=? AND access_key=? ORDER BY updated DESC,id""", org_id, user["id"], key)

    def create(self, user, org_id):
        _, job, key = self.connections.authorized(user, org_id)
        identity, now = secrets.token_hex(16), int(time.time())
        self.store.query("INSERT INTO chats(id,org_id,user_id,access_key,title,created,updated,source_scope,connection_key) VALUES (?,?,?,?,?,?,?,?,?)",
                         identity, org_id, user["id"], key, "گفتگوی جدید", now, now, json.dumps(job["sources"]), job["connection_key"])
        return {"id": identity, "title": "گفتگوی جدید"}

    def owned(self, user, org_id, chat_id):
        member, job, key = self.connections.authorized(user, org_id)
        rows = self.store.query("SELECT * FROM chats WHERE id=? AND org_id=? AND user_id=? AND access_key=?",
                                chat_id, org_id, user["id"], key)
        if not rows:
            raise PortalError("گفتگو پیدا نشد یا دسترسی فعلی آن تغییر کرده است.", 404)
        return rows[0], member, job

    def read(self, user, org_id, chat_id):
        chat, _, _ = self.owned(user, org_id, chat_id)
        turns = self.store.query("SELECT id,question,answer,status,created FROM turns WHERE chat_id=? ORDER BY created,rowid", chat_id)
        return {key: chat[key] for key in ("id", "title", "created", "updated", "busy_turn_id")} | {
            "turns": [{**turn, "answer": json.loads(turn["answer"]) if turn["answer"] else None} for turn in turns]}

    def delete(self, user, org_id, chat_id):
        chat, _, _ = self.owned(user, org_id, chat_id)
        if chat["busy_turn_id"]:
            raise PortalError("ابتدا منتظر پایان پاسخ این گفتگو بمانید.", 409)
        self.store.query("DELETE FROM chats WHERE id=? AND org_id=? AND user_id=? AND busy_turn_id IS NULL", chat_id, org_id, user["id"])
        return {"ok": True}

    def ask(self, user, org_id, chat_id, request_id, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 2000 or not REQUEST_ID.fullmatch(request_id):
            raise PortalError("سؤال یا شناسهٔ درخواست معتبر نیست؛ سؤال حداکثر ۲۰۰۰ کاراکتر باشد.")
        usage.recover(self.store)
        chat, member, job = self.owned(user, org_id, chat_id)
        previous = self.store.query("SELECT id,chat_id,answer,status FROM turns WHERE id=?", request_id)
        if previous:
            if previous[0]["chat_id"] != chat_id:
                raise PortalError("شناسهٔ درخواست در گفتگوی دیگری استفاده شده است.", 409)
            return self._saved(previous[0])
        usage.rate_limit(self.store, org_id, user["id"])
        history = self.read(user, org_id, chat_id)["turns"]
        reservation = usage.reserve(self.store, member, chat_id, request_id, question.strip())
        return self._answer(user, org_id, chat, job, reservation, request_id, question.strip(), history)

    @staticmethod
    def _saved(turn):
        if turn["status"] == "pending":
            raise PortalError("این درخواست هنوز در حال پاسخ‌گویی است؛ دوباره سؤال تازه ارسال نکنید.", 409)
        return {"id": turn["id"], "answer": json.loads(turn["answer"]), "reused": True}

    def _answer(self, user, org_id, chat, job, reservation, request_id, question, history):
        try:
            context = [turn["answer"] for turn in history[-8:] if turn["answer"] and not turn["answer"].get("error")]
            result = self.connections.engine.run({**job, "mode": "answer", "question": question, "history": context})
            _, _, key = self.connections.authorized(user, org_id)
            if key != chat["access_key"]:
                raise PortalError("دسترسی یا اتصال هنگام پاسخ‌گویی تغییر کرد؛ گفتگوی تازه بسازید.", 403)
            answer = result.get("answer") if result.get("ok") else None
            if not isinstance(answer, dict):
                answer = {"question": question, "error": result.get("message", "پاسخ‌گویی کامل نشد.")}
            success = bool(result.get("complete" if self.quota_policy == "complete_answer" else "valid"))
            answer = usage.finish(self.store, reservation, answer, success)
            self.store.query("UPDATE chats SET title=? WHERE id=? AND title='گفتگوی جدید'", question[:80], chat["id"])
            return {"id": request_id, "answer": answer, "reused": False}
        except Exception:
            usage.finish(self.store, reservation, {"question": question, "error": "پاسخ‌گویی کامل نشد؛ سهمیهٔ درخواست برگردانده شد."}, False)
            raise
