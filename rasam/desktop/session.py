"""پرسش‌های یک گفتگو سریالی اجرا می‌شوند؛ خروجی‌ها از همان پاسخ ذخیره‌شده می‌آیند."""

from __future__ import annotations

import threading
import uuid

from rasam import config
from rasam.core.answer import Answer
from rasam.core.chat_store import ChatStore, scope_key


def answer_question(question: str, history=None) -> Answer:
    if config.settings is None:
        return Answer(question=question, error="ابتدا اتصال به دیتابیس را تنظیم کنید.")
    if not all((config.settings.llm_api_key, config.settings.llm_base_url, config.settings.llm_model)):
        return Answer(question=question, error="اتصال دیتابیس آماده است؛ ابتدا سرویس مدل و لایسنس را فعال کنید.")
    from rasam.core.graph import answer
    return answer(question, history=history)


class Session:
    def __init__(self, answerer=None):
        self.answerer = answerer or answer_question
        self.lock = threading.RLock()
        self.last_answer = None
        self.answer_id = None
        self.last_scope = None
        self.chats = ChatStore(config.DATA_HOME / "conversations.sqlite3")

    def ask(self, question: str, chat_id: str | None = None) -> tuple[Answer, str]:
        with self.lock:
            scope = scope_key()
            identity = uuid.uuid4().hex
            history, error = self._history(scope, chat_id)
            if error:
                return Answer(question=question, error=error), identity
            try:
                result = self.answerer(question, history=history) if chat_id else self.answerer(question)
            except Exception:
                result = Answer(question=question, error="پاسخ‌گویی انجام نشد؛ دوباره تلاش کنید.")
            if chat_id:
                saved = self.chats.append(scope, chat_id, identity, result)
                if not saved.ok or not saved.value:
                    result.error = saved.reason or "گفتگو دیگر در دسترس نیست."
            self.last_answer, self.answer_id, self.last_scope = result, identity, scope
            return result, identity

    def _history(self, scope, chat_id):
        if not chat_id:
            return [], ""
        if not scope:
            return [], "ابتدا اتصال دیتابیس را تنظیم کنید."
        stored = self.chats.read(scope, chat_id)
        if not stored.ok:
            return [], stored.reason
        if stored.value is None:
            return [], "گفتگو در این اتصال وجود ندارد؛ گفتگوی تازه‌ای بسازید."
        return [turn["answer"] for turn in stored.value["turns"]], ""

    def result(self, answer_id: str) -> Answer | None:
        with self.lock:
            scope = scope_key()
            if answer_id == self.answer_id and scope == self.last_scope:
                return self.last_answer
            if not scope:
                return None
            if not self.chats.path.exists():
                return None
            saved = self.chats.result(scope, answer_id)
            try:
                return Answer(**saved.value) if saved.ok and saved.value else None
            except (TypeError, ValueError):
                return None

    def is_followup(self, answer_id: str) -> bool:
        with self.lock:
            if not self.chats.path.exists():
                return False
            result = self.chats.is_followup(scope_key(), answer_id)
            return not result.ok or bool(result.value)
