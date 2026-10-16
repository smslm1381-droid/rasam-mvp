"""آخرین پاسخ فقط در حافظه می‌ماند تا خروجی فایل با همان جدول منطبق باشد."""

from __future__ import annotations

import threading
import uuid

from rasam import config
from rasam.core.answer import Answer


def answer_question(question: str) -> Answer:
    if config.settings is None:
        return Answer(question=question, error="ابتدا اتصال به دیتابیس را تنظیم کنید.")
    from rasam.core.graph import answer
    return answer(question)


class Session:
    def __init__(self, answerer=None):
        self.answerer = answerer or answer_question
        self.lock = threading.RLock()
        self.last_answer = None
        self.answer_id = None

    def ask(self, question: str) -> tuple[Answer, str]:
        with self.lock:
            try:
                result = self.answerer(question)
            except Exception:
                result = Answer(question=question, error="پاسخ‌گویی انجام نشد؛ دوباره تلاش کنید.")
            self.last_answer = result
            self.answer_id = uuid.uuid4().hex
            return result, self.answer_id

    def result(self, answer_id: str) -> Answer | None:
        with self.lock:
            return self.last_answer if answer_id == self.answer_id else None
