"""گراف پاسخ‌دادن به یک سوال: ساختن کوئری ← اعتبارسنجی ← اجرا.

چرا گراف و نه یک تابع تودرتو: گره‌های بعدی (خلاصه، نمودار، خودترمیمی) بدون
بازنویسی اضافه می‌شوند. مسیر خطا از هر گره مستقیم به خروجی می‌رود، پس هیچ
کوئری اعتبارسنجی‌نشده‌ای به گره اجرا نمی‌رسد.

هیچ استثنایی از `answer()` بیرون نمی‌رود (قاعده‌ی امنیتی ۷).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pymongo.errors import PyMongoError

import config
import db
import guard
import llm
import prompts


@dataclass
class Answer:
    """آنچه به کاربر برمی‌گردد. لایه‌ی نمایش فقط همین را سریالایز می‌کند.

    تفکیک `message` از `error` عمدی است: «این داده در دیتابیس نیست» خطا نیست،
    یک جواب معتبر است و باید متفاوت نمایش داده شود. قاطی‌کردنشان اشتباه
    نسخه‌ی ۱ بود (docs/v1-reference.md بخش ۴).
    """

    question: str
    collection: str | None = None
    pipeline: list[dict] | None = None
    rows: list[dict] = field(default_factory=list)
    message: str | None = None
    error: str | None = None


class State(TypedDict, total=False):
    """حالت میان گره‌ها. `max_time_ms` از گارد می‌آید و فقط داخلی است."""

    question: str
    collection: str | None
    pipeline: list[dict] | None
    rows: list[dict]
    message: str | None
    error: str | None
    max_time_ms: int


def _parse(text: str) -> tuple[dict | None, str | None]:
    """خروجی مدل را به «کوئری» یا «جمله‌ی فارسی» تفکیک می‌کند.

    قاعده‌ی تشخیص از v1-reference بخش ۴: اگر JSON معتبر بود، تلاش برای کوئری
    بوده؛ وگرنه جمله‌ای است که طبق قاعده‌ی ۵ پرامپت داده شده.

    بلوک markdown با اینکه قاعده‌ی ۶ منعش کرده پاک می‌شود، چون مدل‌ها گاهی
    اضافه‌اش می‌کنند و ردکردن یک کوئری سالم به‌خاطر سه بک‌تیک بی‌دلیل است.
    """
    stripped = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None, text
    return (parsed, None) if isinstance(parsed, dict) else (None, text)


def generate(state: State) -> State:
    """گره ۱ — از سوال، کوئری می‌سازد."""
    try:
        schema = db.describe_schema(db.connect())
    except PyMongoError as error:
        return {"error": f"اتصال به دیتابیس برقرار نشد: {error}"}

    allowed = config.settings.allowed_collections
    reply = llm.ask(prompts.build_query_prompt(schema, state["question"], allowed))
    if not reply.ok:
        return {"error": reply.reason}

    parsed, message = _parse(reply.text)
    if parsed is None:
        return {"message": message}
    return {"collection": parsed.get("collection"), "pipeline": parsed.get("pipeline")}


def validate(state: State) -> State:
    """گره ۲ — گارد. تنها راه رسیدن کوئری به دیتابیس."""
    checked = guard.check(
        state.get("pipeline"),
        state.get("collection") or "",
        set(config.settings.allowed_collections),
    )
    if not checked.ok:
        return {"error": f"کوئری ساخته‌شده پذیرفته نشد: {checked.reason}"}
    return {"pipeline": checked.pipeline, "max_time_ms": checked.max_time_ms}


def execute(state: State) -> State:
    """گره ۳ — اجرای کوئریِ تاییدشده."""
    try:
        database = db.connect()
        rows = list(database[state["collection"]].aggregate(
            state["pipeline"], maxTimeMS=state["max_time_ms"]))
    except PyMongoError as error:
        return {"error": f"اجرای کوئری روی دیتابیس شکست خورد: {error}"}
    return {"rows": rows}


def _next_after(state: State) -> str:
    """هر گره می‌تواند مسیر را همین‌جا تمام کند."""
    return END if state.get("error") or state.get("message") else "continue"


def _build():
    graph = StateGraph(State)
    graph.add_node("generate", generate)
    graph.add_node("validate", validate)
    graph.add_node("execute", execute)
    graph.add_edge(START, "generate")
    graph.add_conditional_edges("generate", _next_after, {"continue": "validate", END: END})
    graph.add_conditional_edges("validate", _next_after, {"continue": "execute", END: END})
    graph.add_edge("execute", END)
    return graph.compile()


_GRAPH = _build()


def answer(question: str) -> Answer:
    """سوال فارسی می‌گیرد و `Answer` برمی‌گرداند. هرگز استثنا پرتاب نمی‌کند."""
    if not question or not question.strip():
        return Answer(question=question, error="سوالی وارد نشده است.")

    try:
        final: dict[str, Any] = _GRAPH.invoke({"question": question})
    except Exception as error:  # noqa: BLE001 — عمدی: آخرین سد قاعده‌ی ۷
        # گره‌ها خطاهای شناخته‌شده را خودشان به مقدار تبدیل می‌کنند. این سد
        # برای چیزی است که پیش‌بینی نکرده‌ایم؛ کاربر نباید stack trace ببیند.
        return Answer(question=question,
                      error=f"خطای پیش‌بینی‌نشده در پاسخ به سوال: {type(error).__name__}")

    return Answer(
        question=question,
        collection=final.get("collection"),
        pipeline=final.get("pipeline"),
        rows=final.get("rows") or [],
        message=final.get("message"),
        error=final.get("error"),
    )
