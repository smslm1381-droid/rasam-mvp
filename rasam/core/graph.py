"""گراف پاسخ‌دادن به یک سوال: ساختن کوئری ← اعتبارسنجی ← اجرا ← خلاصه.

اگر کوئری رد یا اجرایش ناموفق شود، خطا به مدل برمی‌گردد تا خودش اصلاحش کند
(گره `repair`)، حداکثر تا سقف تنظیم‌شده‌ی تلاش‌ها.

چرا گراف و نه یک تابع تودرتو: گره‌های بعدی (خلاصه، نمودار، خودترمیمی) بدون
بازنویسی اضافه می‌شوند. مسیر خطا از هر گره مستقیم به خروجی می‌رود، پس هیچ
کوئری اعتبارسنجی‌نشده‌ای به گره اجرا نمی‌رسد.

هیچ استثنایی از `answer()` بیرون نمی‌رود (قاعده‌ی امنیتی ۷).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from rasam import config
from rasam.core import charting, conversation, knowledge, llm, prompts
from rasam.databases import registry
from rasam.core.answer import Answer
from rasam.databases.base import Result

class State(TypedDict, total=False):
    """حالت میان گره‌ها. `max_time_ms` از گارد می‌آید و فقط داخلی است."""

    question: str
    source: str | None
    query: Any
    checked: Result
    rows: list[dict]
    summary: str | None
    chart: dict[str, Any] | None
    want_chart: bool
    attempts: int
    repaired: bool
    message: str | None
    error: str | None


def generate(state: State) -> State:
    """گره ۱ — از سوال، کوئری می‌سازد."""
    try:
        schema = registry.get_agent().describe_schema()
    except Exception as error:  # noqa: BLE001 — backend خطا را به مقدار تبدیل می‌کند
        return {"error": f"اتصال به دیتابیس برقرار نشد ({type(error).__name__}). آدرس و دسترسی اتصال را بررسی کنید."}

    selected = _knowledge(state["question"], schema)
    agent = registry.get_agent()
    reply = llm.ask(agent.build_query_prompt(
        selected["schema"], state["question"], config.settings.allowed_sources,
        want_chart=state.get("want_chart", False),
        documentation=selected["documentation"], examples=selected["examples"]))
    if not reply.ok:
        return {"error": reply.reason}

    parsed = agent.parse_reply(reply.text)
    if parsed.error:
        return {"error": parsed.error}
    if parsed.message:
        return {"message": parsed.message}
    return {"source": parsed.source, "query": parsed.query, "attempts": 1}


def prepare(state: State) -> State:
    """پیام گفت‌وگویی بدون مدل/دیتابیس پاسخ می‌گیرد؛ بقیه به مسیر کوئری می‌روند."""
    message = conversation.reply(state["question"])
    if message:
        return {"message": message}
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
         "documentation": knowledge.documentation_text(),
         "examples": knowledge.examples_text(registry.get_agent().format_example)},
        config.settings.max_knowledge_chars,
    )


@lru_cache(maxsize=8)
def _knowledge_store(schema: str) -> knowledge.KnowledgeStore:
    store = knowledge.KnowledgeStore(
        config.settings.customer.name,
        config.CHROMA_DIR,
    )
    store.rebuild(schema, config.settings.customer.directory)
    return store


def validate(state: State) -> State:
    """گره ۲ — گارد. تنها راه رسیدن کوئری به دیتابیس."""
    agent = registry.get_agent()
    checked = agent.validate_query(state.get("source") or "", state.get("query"))
    if not checked.ok:
        return {"error": f"کوئری ساخته‌شده پذیرفته نشد: {checked.reason}"}
    return {"query": checked.query, "checked": checked}


def execute(state: State) -> State:
    """گره ۳ — اجرای کوئریِ تاییدشده."""
    try:
        rows = registry.get_agent().execute(state["source"], state["checked"])
    except Exception as error:  # noqa: BLE001 — backend خطا را به مقدار تبدیل می‌کند
        # پیام درایور ممکن است آدرس و رمز داشته باشد؛ حتی به مدل ترمیم نمی‌رود.
        return {"error": f"اجرای کوئری روی دیتابیس شکست خورد ({type(error).__name__}). ساختار کوئری و دسترسی خواندن را بررسی کنید."}
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

    selected = _knowledge(state["question"], schema)
    agent = registry.get_agent()
    reply = llm.ask(agent.build_query_prompt(
        selected["schema"], state["question"], config.settings.allowed_sources,
        want_chart=state.get("want_chart", False),
        documentation=selected["documentation"], examples=selected["examples"],
        failure=(state.get("query"), state.get("error") or ""),
    ))
    if not reply.ok:
        return {"attempts": attempts}

    parsed = agent.parse_reply(reply.text)
    if parsed.error:
        return {"attempts": attempts, "error": parsed.error}
    if parsed.message:
        # مدل به این نتیجه رسیده که سوال از این داده قابل جواب نیست.
        return {"attempts": attempts, "message": parsed.message, "error": None}
    return {"attempts": attempts, "repaired": True, "error": None,
            "source": parsed.source, "query": parsed.query}


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


def graph_nodes(capabilities: set[str] | frozenset[str]) -> list[str]:
    """گره‌های گرافِ یک مشتری، به ترتیب مسیر.

    هسته (چهار گره‌ی اول) همیشه هست؛ بقیه فقط اگر قابلیتشان در پروفایل آمده
    باشد. هم `build_graph` از همین فهرست می‌سازد و هم خط فرمان آن را چاپ می‌کند،
    تا «چه گره‌هایی دارد» یک جواب داشته باشد.
    """
    optional = [("summarize", "summary"), ("chart", "chart"), ("repair", "repair")]
    return ["prepare", "generate", "validate", "execute"] + [
        node for node, capability in optional if capability in capabilities
    ]


def _chart_if_wanted(state: State, nodes: list[str]) -> str:
    """فقط سوالی که نمودار خواسته باشد، و مشتری‌ای که نمودار دارد، به آن می‌رسد."""
    return "chart" if "chart" in nodes and state.get("want_chart") else END


def _route(state: State, on_success: str, on_failure: str) -> str:
    """بعد از اعتبارسنجی یا اجرا: موفقیت، شانس دوم، یا پایان."""
    outcome = _next_or_repair(state)
    if outcome == "continue":
        return on_success
    return on_failure if outcome == "repair" else END


def build_graph(capabilities: set[str] | frozenset[str]):
    """گراف را از روی قابلیت‌های مشتری می‌سازد.

    گره‌ای که مشتری نخواسته **اصلاً ساخته نمی‌شود**، نه اینکه باشد و رد کند.
    هسته‌ی `prepare ← generate ← validate ← execute` قابلیت نیست و هرگز خاموش
    نمی‌شود: گارد یک گزینه نیست. مشتری بدون `repair` شانس دوم ندارد: کوئری
    ردشده یا ناموفق مستقیم به پایان (و خطا) می‌رود.
    """
    nodes = graph_nodes(capabilities)
    functions = {"prepare": prepare, "generate": generate, "validate": validate,
                 "execute": execute, "summarize": summarize, "chart": chart,
                 "repair": repair}
    graph = StateGraph(State)
    for node in nodes:
        graph.add_node(node, functions[node])

    on_failure = "repair" if "repair" in nodes else END

    def after_execute(state: State) -> str:
        after_rows = "summarize" if "summarize" in nodes else _chart_if_wanted(state, nodes)
        return _route(state, after_rows, on_failure)

    graph.add_edge(START, "prepare")
    graph.add_conditional_edges("prepare", _next_after, {"continue": "generate", END: END})
    graph.add_conditional_edges("generate", _next_after, {"continue": "validate", END: END})
    graph.add_conditional_edges("validate", lambda state: _route(state, "execute", on_failure))
    graph.add_conditional_edges("execute", after_execute)
    if "repair" in nodes:
        # ترمیم همیشه به اعتبارسنجی برمی‌گردد: هیچ کوئری اصلاح‌شده‌ای بدون
        # گذشتن از گارد اجرا نمی‌شود.
        graph.add_conditional_edges("repair", _next_after, {"continue": "validate", END: END})
    if "summarize" in nodes:
        graph.add_conditional_edges("summarize", lambda state: _chart_if_wanted(state, nodes))
    if "chart" in nodes:
        graph.add_edge("chart", END)
    return graph.compile()


registry.check_db_type(config.settings.customer)
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
        source=final.get("source"),
        query=final.get("query"),
        rows=final.get("rows") or [],
        summary=final.get("summary"),
        chart=final.get("chart"),
        repaired=bool(final.get("repaired")),
        message=final.get("message"),
        error=final.get("error"),
    )
