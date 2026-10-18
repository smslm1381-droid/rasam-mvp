"""گفتگو روی همان دستگاه می‌ماند؛ هر اتصال فضای جدا و هر پیام شناسهٔ پایدار دارد."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid
from urllib.parse import urlsplit

from rasam import config


@dataclass
class Stored:
    value: object = None
    reason: str = ""

    @property
    def ok(self):
        return not self.reason


def scope_key() -> str | None:
    settings = config.settings
    if settings is None:
        return None
    address = urlsplit(settings.connection_uri)
    # تغییر رمز نباید گفتگو را گم کند؛ تغییر مشتری/مقصد/منابع نباید سابقه را نشت دهد.
    identity = [str(settings.customer.directory.resolve()), settings.customer.db_type,
                settings.database, address.hostname, address.port, address.username,
                sorted(settings.allowed_sources)]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


class ChatStore:
    def __init__(self, path: Path):
        self.path = path

    def _run(self, work):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch(mode=0o600, exist_ok=True)
            with sqlite3.connect(self.path, timeout=5) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA foreign_keys = ON")
                db.execute("CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, scope TEXT NOT NULL, title TEXT NOT NULL, updated TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, chat TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE, answer TEXT NOT NULL, created TEXT NOT NULL)")
                return Stored(work(db))
        except (OSError, sqlite3.Error, ValueError, TypeError):
            return Stored(reason="خواندن یا ذخیرهٔ گفتگو ممکن نشد؛ فضای خالی و دسترسی پوشهٔ برنامه را بررسی کنید.")

    def list(self, scope):
        return self._run(lambda db: [dict(row) for row in db.execute(
            "SELECT id,title,updated FROM chats WHERE scope=? ORDER BY updated DESC", (scope,))])

    def create(self, scope):
        def work(db):
            chat = {"id": uuid.uuid4().hex, "title": "گفتگوی جدید", "updated": datetime.now(timezone.utc).isoformat()}
            db.execute("INSERT INTO chats VALUES (?,?,?,?)", (chat["id"], scope, chat["title"], chat["updated"]))
            return chat
        return self._run(work)

    def read(self, scope, chat_id):
        def work(db):
            chat = db.execute("SELECT id,title,updated FROM chats WHERE id=? AND scope=?", (chat_id, scope)).fetchone()
            if chat is None:
                return None
            turns = db.execute("SELECT id,answer,created FROM turns WHERE chat=? ORDER BY rowid", (chat_id,))
            return {**dict(chat), "turns": [{"id": row["id"], "answer": json.loads(row["answer"]), "created": row["created"]} for row in turns]}
        return self._run(work)

    def append(self, scope, chat_id, answer_id, answer):
        def work(db):
            now = datetime.now(timezone.utc).isoformat()
            row = db.execute("SELECT title FROM chats WHERE id=? AND scope=?", (chat_id, scope)).fetchone()
            if row is None:
                return False
            payload = json.dumps(asdict(answer), ensure_ascii=False, allow_nan=False, default=_json_value)
            db.execute("INSERT INTO turns VALUES (?,?,?,?)", (answer_id, chat_id, payload, now))
            title = answer.question[:80] if row["title"] == "گفتگوی جدید" else row["title"]
            db.execute("UPDATE chats SET title=?,updated=? WHERE id=?", (title, now, chat_id))
            return True
        return self._run(work)

    def result(self, scope, answer_id):
        def work(db):
            row = db.execute("SELECT answer FROM turns JOIN chats ON turns.chat=chats.id WHERE turns.id=? AND chats.scope=?", (answer_id, scope)).fetchone()
            return json.loads(row["answer"]) if row else None
        return self._run(work)

    def delete(self, scope, chat_id):
        return self._run(lambda db: bool(db.execute("DELETE FROM chats WHERE id=? AND scope=?", (chat_id, scope)).rowcount))

    def is_followup(self, scope, answer_id):
        def work(db):
            row = db.execute(
                "SELECT EXISTS (SELECT 1 FROM turns prior WHERE prior.chat=t.chat AND prior.rowid<t.rowid) "
                "FROM turns t JOIN chats c ON t.chat=c.id WHERE t.id=? AND c.scope=?",
                (answer_id, scope)).fetchone()
            return bool(row[0]) if row else False
        return self._run(work)
