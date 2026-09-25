"""گراف پاسخ‌دادن به یک سوال: ساختن کوئری ← اعتبارسنجی ← اجرا ← خلاصه.

اگر کوئری رد یا اجرایش ناموفق شود، خطا به مدل برمی‌گردد تا خودش اصلاحش کند
(گره `repair`)، حداکثر تا سقف تنظیم‌شده‌ی تلاش‌ها.

چرا گراف و نه یک تابع تودرتو: گره‌های بعدی (خلاصه، نمودار، خودترمیمی) بدون
بازنویسی اضافه می‌شوند. مسیر خطا از هر گره مستقیم به خروجی می‌رود، پس هیچ
کوئری اعتبارسنجی‌نشده‌ای به گره اجرا نمی‌رسد.

هیچ استثنایی از `answer()` بیرون نمی‌رود (قاعده‌ی امنیتی ۷).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

import config
import charting
import knowledge_store
import llm
import prompts
from agents import registry

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
    chart: dict[str, Any] | None = None
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
    chart: dict[str, Any] | None
    want_chart: bool
    attempts: int
    repaired: bool
    message: str | None
    error: str | None
    max_time_ms: int


# نشانه‌ی اینکه مدل *قصد* کوئری داشته، حتی اگر نتیجه JSON معتبری نباشد.
_JSON_START = ("{", "[")

_BROKEN_JSON = (
    "مدل چیزی شبیه کوئری برگرداند که JSON معتبری نبود. "
    "دوباره بپرسید؛ اگر تکرار شد، مدل تنظیم‌شده در RASAM_LLM_MODEL را عوض کنید."
)


def _balanced_object(text: str) -> str | None:
    """از اولین `{`، تا آکولادِ متناظرش را برمی‌گرداند.

    چرا لازم شد: بعضی مدل‌ها بعد از شیء JSON چیز اضافه می‌گذارند — یک `}`
    زیادی، یک جمله‌ی توضیح، یا متن فکرکردنشان. `json.loads` روی کل متن شکست
    می‌خورد و یک کوئریِ کاملاً درست دور ریخته می‌شود.

    این *حدس زدن* نیست: فقط آکولادها شمرده می‌شوند و رشته‌های داخل JSON (که
    ممکن است خودشان آکولاد داشته باشند) رد می‌شوند. چیزی که برمی‌گردد باز هم
    باید از `json.loads` و بعد از گارد رد شود.
    """
    start = text.find("{")
    if start < 0:
        return None

    depth, in_string, escaped = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def _parse(text: str) -> tuple[dict | None, str | None, str | None]:
    """خروجی مدل را سه‌راهی تفکیک می‌کند: کوئری، جمله‌ی فارسی، یا خطا.

    قاعده‌ی تشخیص از v1-reference بخش ۴: اگر JSON معتبر بود، تلاش برای کوئری
    بوده؛ وگرنه جمله‌ای است که طبق قاعده‌ی ۵ پرامپت داده شده.

    حالت سوم از یک شکست واقعی آمد: مدلی یک `}` اضافه در جواب گذاشت، JSON از هم
    پاشید، و آن متن به‌عنوان «جمله‌ی فارسی» پذیرفته شد — کاربر به‌جای جواب، یک
    خط JSON خام دید و برنامه آن را موفقیت شمرد. پس متنی که با `{` یا `[` شروع
    می‌شود هرگز جمله نیست: یا کوئری است یا خطا.

    بلوک markdown با اینکه قاعده‌ی ۶ منعش کرده پاک می‌شود، چون مدل‌ها گاهی
    اضافه‌اش می‌کنند و ردکردن یک کوئری سالم به‌خاطر سه بک‌تیک بی‌دلیل است.
    """
    stripped = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = _retry_as_object(stripped)
        if parsed is None:
            if stripped.startswith(_JSON_START):
                return None, None, _BROKEN_JSON
            return None, text, None
    if isinstance(parsed, dict):
        return parsed, None, None
    # JSON معتبر ولی نه یک شیء: مثلاً فقط pipeline بدون نام کالکشن.
    return None, None, _BROKEN_JSON


def _retry_as_object(text: str) -> dict | None:
    """تلاش دوم: فقط شیء JSON را از دل متن بیرون بکش و همان را بخوان."""
    candidate = _balanced_object(text)
    if candidate is None:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def generate(state: State) -> State:
    """گره ۱ — از سوال، کوئری می‌سازد."""
    try:
        schema = registry.get_agent().describe_schema()
    except Exception as error:  # noqa: BLE001 — backend خطا را به مقدار تبدیل می‌کند
        return {"error": f"اتصال به دیتابیس برقرار نشد: {error}"}

    knowledge = _knowledge(state["question"], schema)
    allowed = config.settings.allowed_collections
    reply = llm.ask(prompts.build_query_prompt(
        knowledge["schema"], state["question"], allowed,
        want_chart=state.get("want_chart", False),
        documentation=knowledge["documentation"], examples=knowledge["examples"]))
    if not reply.ok:
        return {"error": reply.reason}

    parsed, message, error = _parse(reply.text)
    if error:
        return {"error": error}
    if parsed is None:
        return {"message": message}
    return {"collection": parsed.get("collection"), "pipeline": parsed.get("pipeline"),
            "attempts": 1}


def prepare(state: State) -> State:
    """پیش از تماس با مدل، خواست صریح نمودار را ثبت می‌کند."""
    return {"want_chart": (
        "chart" in config.settings.customer.capabilities
        and charting.wants_chart(state["question"]))}


def _knowledge(question: str, schema: str) -> dict[str, str]:
    """سه بخش دانشِ ورودی پرامپت: ساختار، مستندات، نمونه‌ها.

    تا وقتی در بودجه جا می‌شوند کامل می‌روند؛ از آن به بعد شاخص معنایی
    مرتبط‌ترین‌ها را انتخاب می‌کند (`KnowledgeStore.select`).
    """
    return _knowledge_store(schema).select(
        question,
        {"schema": schema,
         "documentation": prompts.documentation_text(),
         "examples": prompts.examples_text()},
        config.settings.max_knowledge_chars,
    )


@lru_cache(maxsize=8)
def _knowledge_store(schema: str) -> knowledge_store.KnowledgeStore:
    store = knowledge_store.KnowledgeStore(
        config.settings.customer.name,
        config.PROJECT_ROOT / "chroma",
    )
    store.rebuild(schema, config.PROJECT_ROOT / "knowledge")
    return store


def validate(state: State) -> State:
    """گره ۲ — گارد. تنها راه رسیدن کوئری به دیتابیس."""
    agent = registry.get_agent()
    checked = agent.validate_query(state.get("collection") or "", state.get("pipeline"))
    if not checked.ok:
        return {"error": f"کوئری ساخته‌شده پذیرفته نشد: {checked.reason}"}
    return {"pipeline": checked.pipeline, "max_time_ms": checked.max_time_ms}


def execute(state: State) -> State:
    """گره ۳ — اجرای کوئریِ تاییدشده."""
    try:
        rows = registry.get_agent().execute(
            state["collection"], state["pipeline"], state["max_time_ms"])
    except Exception as error:  # noqa: BLE001 — backend خطا را به مقدار تبدیل می‌کند
        return {"error": f"اجرای کوئری روی دیتابیس شکست خورد: {error}"}
    return {"rows": rows}


def repair(state: State) -> State:
    """گره ترمیم — کوئری ردشده و دلیلش را به مدل برمی‌گرداند تا اصلاح کند.

    شمارنده‌ی تلاش‌ها **همیشه** بالا می‌رود، حتی وقتی خودِ ترمیم شکست بخورد؛
    وگرنه گراف بین اعتبارسنجی و ترمیم گیر می‌کند.
    """
    attempts = state.get("attempts", 1) + 1
    try:
        schema = registry.get_agent().describe_schema()
    except Exception:  # noqa: BLE001 — ترمیم در تلاش بعدی دوباره امتحان می‌شود
        return {"attempts": attempts}

    knowledge = _knowledge(state["question"], schema)
    reply = llm.ask(prompts.build_query_prompt(
        knowledge["schema"], state["question"], config.settings.allowed_collections,
        want_chart=state.get("want_chart", False),
        documentation=knowledge["documentation"], examples=knowledge["examples"],
        failure=(state.get("pipeline"), state.get("error") or ""),
    ))
    if not reply.ok:
        return {"attempts": attempts}

    parsed, message, error = _parse(reply.text)
    if error:
        return {"attempts": attempts, "error": error}
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


def chart(state: State) -> State:
    """گره نمودار: ابتدا بررسی محلی، سپس دریافت و پاک‌سازی مشخصات مدل."""
    rows = state.get("rows") or []
    possible, _ = charting.local_check(rows)
    if not possible:
        return {"chart": None}
    reply = llm.ask(charting.build_prompt(state["question"], rows))
    if not reply.ok:
        return {"chart": None}
    return {"chart": charting.parse_and_validate(reply.text or "", rows)}


def _next_after(state: State) -> str:
    """بعد از گره تولید: یا ادامه، یا پایان."""
    return END if state.get("error") or state.get("message") else "continue"


def _next_or_repair(state: State) -> str:
    """بعد از اعتبارسنجی و اجرا: خطا یعنی یک شانس دیگر، تا سقف تلاش‌ها."""
    if state.get("message"):
        return END
    if not state.get("error"):
        return "continue"
    return "repair" if state.get("attempts", 1) < config.settings.max_attempts else END


def _next_after_summary(state: State) -> str:
    """فقط سوالی که نمودار خواسته باشد به گره نمودار می‌رسد."""
    return "chart" if state.get("want_chart") else END


def build_graph(capabilities: set[str] | frozenset[str]):
    graph = StateGraph(State)
    graph.add_node("prepare", prepare)
    graph.add_node("generate", generate)
    graph.add_node("validate", validate)
    graph.add_node("execute", execute)
    graph.add_node("summarize", summarize)
    graph.add_node("repair", repair)
    if "chart" in capabilities:
        graph.add_node("chart", chart)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "generate")
    graph.add_conditional_edges("generate", _next_after, {"continue": "validate", END: END})
    graph.add_conditional_edges("validate", _next_or_repair,
                                {"continue": "execute", "repair": "repair", END: END})
    graph.add_conditional_edges("execute", _next_or_repair,
                                {"continue": "summarize", "repair": "repair", END: END})
    # ترمیم همیشه به اعتبارسنجی برمی‌گردد: هیچ کوئری اصلاح‌شده‌ای بدون گذشتن
    # از گارد اجرا نمی‌شود.
    graph.add_conditional_edges("repair", _next_after, {"continue": "validate", END: END})
    if "chart" in capabilities:
        graph.add_conditional_edges("summarize", _next_after_summary,
                                    {"chart": "chart", END: END})
        graph.add_edge("chart", END)
    else:
        graph.add_edge("summarize", END)
    return graph.compile()


_GRAPH = build_graph(config.settings.customer.capabilities)


def answer(question: str) -> Answer:
    """سوال فارسی می‌گیرد و `Answer` برمی‌گرداند. هرگز استثنا پرتاب نمی‌کند."""
    if not question or not question.strip():
        return Answer(question=question, error="سوالی وارد نشده است.")

    # سوال بلند بریده نمی‌شود، رد می‌شود. سوالِ نصفه جوابِ نصفه می‌دهد و کاربر
    # هیچ‌وقت نمی‌فهمد چرا؛ بهتر است همین‌جا صریح بگوییم.
    if len(question) > config.settings.max_question_chars:
        return Answer(question=question, error=(
            f"سوال شما {len(question)} کاراکتر است و از سقف "
            f"{config.settings.max_question_chars} کاراکتر بیشتر است. "
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
        chart=final.get("chart"),
        repaired=bool(final.get("repaired")),
        message=final.get("message"),
        error=final.get("error"),
    )
