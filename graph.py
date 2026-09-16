"""گراف پاسخ‌دادن به یک سوال: ساختن کوئری ← اعتبارسنجی ← اجرا ← خلاصه.

اگر کوئری رد یا اجرایش ناموفق شود، خطا به مدل برمی‌گردد تا خودش اصلاحش کند
(گره `repair`)، حداکثر تا سقف `MAX_ATTEMPTS` تلاش.

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

# تلاش اول + یک ترمیم. سقف داشتن اجباری است: بدون آن یک کوئری که مدل مدام
# اشتباه می‌سازد، بی‌نهایت بار به سرویس می‌رود.
MAX_ATTEMPTS = 2


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
    summary: str | None = None
    # آیا جواب بعد از یک بار اصلاح به دست آمد. برای کاربر یعنی «این جواب
    # ارزان به دست نیامد»، و برای ما نشانه‌ای که پرامپت جای بهترشدن دارد.
    repaired: bool = False
    message: str | None = None
    error: str | None = None


class State(TypedDict, total=False):
    """حالت میان گره‌ها. `max_time_ms` از گارد می‌آید و فقط داخلی است."""

    question: str
    collection: str | None
    pipeline: list[dict] | None
    rows: list[dict]
    summary: str | None
    attempts: int
    repaired: bool
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
    return {"collection": parsed.get("collection"), "pipeline": parsed.get("pipeline"),
            "attempts": 1}


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


def repair(state: State) -> State:
    """گره ترمیم — کوئری ردشده و دلیلش را به مدل برمی‌گرداند تا اصلاح کند.

    شمارنده‌ی تلاش‌ها **همیشه** بالا می‌رود، حتی وقتی خودِ ترمیم شکست بخورد؛
    وگرنه گراف بین اعتبارسنجی و ترمیم گیر می‌کند.
    """
    attempts = state.get("attempts", 1) + 1
    try:
        schema = db.describe_schema(db.connect())
    except PyMongoError:
        return {"attempts": attempts}

    reply = llm.ask(prompts.build_query_prompt(
        schema, state["question"], config.settings.allowed_collections,
        failure=(state.get("pipeline"), state.get("error") or ""),
    ))
    if not reply.ok:
        return {"attempts": attempts}

    parsed, message = _parse(reply.text)
    if parsed is None:
        # مدل به این نتیجه رسیده که سوال از این داده قابل جواب نیست.
        return {"attempts": attempts, "message": message, "error": None}
    return {"attempts": attempts, "repaired": True, "error": None,
            "collection": parsed.get("collection"), "pipeline": parsed.get("pipeline")}


def summarize(state: State) -> State:
    """گره ۴ — یک یا دو جمله‌ی فارسی که بگوید نتیجه چه می‌گوید.

    شکست این گره کل پاسخ را از بین نمی‌برد: جدول نتیجه هنوز ارزش دارد
    (docs/v1-reference.md بخش ۴). پس به‌جای `error`، فقط خلاصه خالی می‌ماند.
    """
    reply = llm.ask(prompts.build_summary_prompt(state["question"], state.get("rows") or []))
    return {"summary": reply.text if reply.ok else None}


def _next_after(state: State) -> str:
    """بعد از گره تولید: یا ادامه، یا پایان."""
    return END if state.get("error") or state.get("message") else "continue"


def _next_or_repair(state: State) -> str:
    """بعد از اعتبارسنجی و اجرا: خطا یعنی یک شانس دیگر، تا سقف تلاش‌ها."""
    if state.get("message"):
        return END
    if not state.get("error"):
        return "continue"
    return "repair" if state.get("attempts", 1) < MAX_ATTEMPTS else END


def _build():
    graph = StateGraph(State)
    graph.add_node("generate", generate)
    graph.add_node("validate", validate)
    graph.add_node("execute", execute)
    graph.add_node("summarize", summarize)
    graph.add_node("repair", repair)
    graph.add_edge(START, "generate")
    graph.add_conditional_edges("generate", _next_after, {"continue": "validate", END: END})
    graph.add_conditional_edges("validate", _next_or_repair,
                                {"continue": "execute", "repair": "repair", END: END})
    graph.add_conditional_edges("execute", _next_or_repair,
                                {"continue": "summarize", "repair": "repair", END: END})
    # ترمیم همیشه به اعتبارسنجی برمی‌گردد: هیچ کوئری اصلاح‌شده‌ای بدون گذشتن
    # از گارد اجرا نمی‌شود.
    graph.add_conditional_edges("repair", _next_after, {"continue": "validate", END: END})
    graph.add_edge("summarize", END)
    return graph.compile()


_GRAPH = _build()


def answer(question: str) -> Answer:
    """سوال فارسی می‌گیرد و `Answer` برمی‌گرداند. هرگز استثنا پرتاب نمی‌کند."""
    if not question or not question.strip():
        return Answer(question=question, error="سوالی وارد نشده است.")

    # سوال بلند بریده نمی‌شود، رد می‌شود. سوالِ نصفه جوابِ نصفه می‌دهد و کاربر
    # هیچ‌وقت نمی‌فهمد چرا؛ بهتر است همین‌جا صریح بگوییم.
    if len(question) > prompts.MAX_QUESTION_CHARS:
        return Answer(question=question, error=(
            f"سوال شما {len(question)} کاراکتر است و از سقف "
            f"{prompts.MAX_QUESTION_CHARS} کاراکتر بیشتر است. "
            "لطفاً کوتاه‌ترش کنید و دوباره بپرسید."))

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
        summary=final.get("summary"),
        repaired=bool(final.get("repaired")),
        message=final.get("message"),
        error=final.get("error"),
    )
