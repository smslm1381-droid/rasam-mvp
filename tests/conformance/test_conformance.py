"""آزمون انطباق مشترک: «آداپتور امن» یعنی چه.

قواعد امنیتی بخش ۴ `PLAN.md` برای *هر* دیتابیس باید تست باشند، نه قول. این فایل
روی **هر آداپتور ثبت‌شده در رجیستری** اجرا می‌شود و نمونه‌های حمله را از
`rasam/databases/<نوع>/attacks.yaml` می‌خواند. آداپتوری که این آزمون را سبز
نکند در رجیستری نمی‌ماند (تصمیم ۶۶).

دو نوع ادعا:
- **ساختاری** (بی‌نیاز از دیتابیس): هر حمله رد؛ هر کوئری سالم قبول؛ هیچ ورودی
  استثنا نمی‌دهد؛ و هر دسته‌ی حمله نمونه دارد یا دلیل `not_applicable`.
- **رفتاری** (روی دیتابیس محلی): با سقف رکورد ۵، بیش از ۵ ردیف برنمی‌گردد؛ و
  با شرط سطری، هیچ ردیفی بیرون از شرط برنمی‌گردد. اگر دیتابیس محلی بالا نیست
  با پیام روشن skip می‌شود، نه بی‌صدا سبز.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from rasam import config
from rasam.databases import registry
from tests.conformance.local import LOCAL

DATABASES_DIR = Path(registry.__file__).parent

# دسته‌ها مشترک‌اند و اینجا، در کد، تعریف می‌شوند، نه در فایل هر دیتابیس: اگر
# فایل یک آداپتور دسته‌ای را جا بیندازد یا از خودش بسازد، آزمون قرمز می‌شود.
REJECTED = ("write", "code_execution", "unauthorized_source", "multi_statement")
BOUNDED = ("unbounded_query", "row_filter_bypass")
CATEGORIES = REJECTED + BOUNDED

FORBIDDEN_SOURCE = "billing"
ROW_CAP = 5

GARBAGE_QUERIES = [None, 0, "", "SELECT 1", [], {}, [None], [[]], [{}], {"a": 1},
                   [{"$match": None}], [{"": 1}], [{1: 2}], [{"$match": {"$": 1}}],
                   [{"$match": {}} for _ in range(500)],
                   [{"$match": {"a": {"b": {"c": {"d": {"e": 1}}}}}}], "x" * 100_000]
GARBAGE_SOURCES = [None, "", 0, "no/such source", "\x00", ["a"], {"a": 1}]


def attacks_file(db_type: str) -> Path:
    return DATABASES_DIR / db_type / "attacks.yaml"


def load(db_type: str) -> dict:
    return yaml.safe_load(attacks_file(db_type).read_text(encoding="utf-8"))


def tokens(db_type: str) -> dict[str, str]:
    allowed = sorted(config.settings.allowed_sources)[0]
    local = LOCAL.get(db_type, {})
    return {
        "@allowed": local.get("source", allowed),
        "@forbidden": FORBIDDEN_SOURCE,
        "@filter_field": local.get("filter_field", "filter_field"),
        "@filter_value": local.get("filter_value", "filter_value"),
    }


def resolve(node, mapping: dict[str, str]):
    """نشانه‌ها را، هم در مقدارها و هم در کلیدها، جایگزین می‌کند."""
    if isinstance(node, str):
        # نشانه‌ها داخل متن هم جایگزین می‌شوند (کوئری SQL یک رشته است). نشانه‌های
        # بلندتر اول، تا `@filter_value` پیش از نشانه‌ی کوتاه‌تر دیگری نخورد.
        for token in sorted(mapping, key=len, reverse=True):
            node = node.replace(token, mapping[token])
        return node
    if isinstance(node, list):
        return [resolve(item, mapping) for item in node]
    if isinstance(node, dict):
        return {resolve(key, mapping): resolve(value, mapping) for key, value in node.items()}
    return node


def cases(db_type: str, category: str) -> list:
    entry = load(db_type)["categories"][category]
    mapping = tokens(db_type)
    return [(item["description"], resolve(item["source"], mapping), resolve(item["query"], mapping))
            for item in entry.get("attacks", [])]


def every(categories: tuple[str, ...]):
    """(نوع دیتابیس، دسته، توضیح، منبع، کوئری) برای پارامتری‌کردن تست‌ها."""
    return [
        pytest.param(db_type, category, source, query, id=f"{db_type}-{category}-{index}")
        for db_type in registry.AGENTS
        for category in categories
        for index, (_, source, query) in enumerate(cases(db_type, category))
    ]


def agent_for(db_type: str):
    return registry.AGENTS[db_type]()


db_types = pytest.mark.parametrize("db_type", sorted(registry.AGENTS))


# --- ساختار فایل نمونه‌ها -----------------------------------------------------

@db_types
def test_every_registered_adapter_ships_an_attack_file(db_type):
    assert attacks_file(db_type).is_file(), (
        f"آداپتور «{db_type}» در رجیستری است ولی {attacks_file(db_type)} را ندارد.")


@db_types
def test_the_attack_file_has_exactly_the_shared_categories(db_type):
    categories = load(db_type)["categories"]
    assert set(categories) == set(CATEGORIES), (
        "دسته‌های فایل باید دقیقاً همین‌ها باشند: " + ", ".join(CATEGORIES))


@db_types
@pytest.mark.parametrize("category", CATEGORIES)
def test_each_category_has_attacks_or_a_written_reason_it_does_not_apply(db_type, category):
    """خالی‌گذاشتن یک دسته شکست است؛ کنار گذاشتنش فقط با دلیل."""
    entry = load(db_type)["categories"][category]
    reason = entry.get("not_applicable")
    attacks = entry.get("attacks")
    if reason is not None:
        assert isinstance(reason, str) and len(reason.strip()) >= 20, "دلیل not_applicable باید جمله‌ی کامل باشد"
        assert not attacks, "دسته‌ای که not_applicable است نمونه‌ی حمله نباید داشته باشد"
    else:
        assert attacks, f"دسته‌ی «{category}» نه نمونه‌ای دارد نه دلیلِ not_applicable"
        assert all(item.get("description") and "source" in item and "query" in item for item in attacks)


@db_types
def test_the_declared_kind_matches_the_shared_definition(db_type):
    for category in CATEGORIES:
        expected = "rejected" if category in REJECTED else "bounded"
        assert load(db_type)["categories"][category].get("kind") == expected


@db_types
def test_there_are_several_safe_queries(db_type):
    """وگرنه گاردی که همه‌چیز را رد کند هم سبز می‌شد."""
    assert len(load(db_type)["safe"]) >= 3


def test_the_forbidden_source_is_really_not_allowed():
    assert FORBIDDEN_SOURCE not in config.settings.allowed_sources


# --- ادعاهای ساختاری --------------------------------------------------------

@pytest.mark.parametrize("db_type, category, source, query", every(REJECTED))
def test_every_attack_is_rejected_and_leaves_no_query_behind(db_type, category, source, query):
    result = agent_for(db_type).validate_query(source, query)
    assert result.ok is False, f"حمله‌ی دسته‌ی «{category}» قبول شد: {query}"
    assert result.query is None  # فراموشی `ok` باید بشکند، نه اجرا کند
    assert isinstance(result.reason, str) and result.reason.strip()


@pytest.mark.parametrize("db_type, category, source, query", every(BOUNDED))
def test_a_bounded_attack_is_rejected_or_accepted_with_a_real_query(db_type, category, source, query):
    result = agent_for(db_type).validate_query(source, query)
    if result.ok:
        assert result.query is not None and result.max_time_ms > 0
    else:
        assert result.query is None


@db_types
def test_every_safe_query_is_accepted(db_type):
    mapping = tokens(db_type)
    for item in load(db_type)["safe"]:
        result = agent_for(db_type).validate_query(
            resolve(item["source"], mapping), resolve(item["query"], mapping))
        assert result.ok, f"«{item['description']}» رد شد: {result.reason}"
        assert result.query is not None and result.max_time_ms > 0


@db_types
def test_validate_query_never_raises(db_type):
    """قاعده‌ی ۷: خطا مقدار است. ورودی آشغال هم باید `Result` رد بدهد، نه استثنا."""
    agent = agent_for(db_type)
    allowed = tokens(db_type)["@allowed"]
    for query in GARBAGE_QUERIES:
        result = agent.validate_query(allowed, query)
        assert result.ok is False or result.query is not None
    for source in GARBAGE_SOURCES:
        result = agent.validate_query(source, GARBAGE_QUERIES[8])
        assert result.ok is False and result.query is None


# --- ادعاهای رفتاری روی دیتابیس محلی ----------------------------------------

@pytest.fixture
def local(request):
    """دیتابیس محلی آماده، یا skip با دلیل روشن."""
    db_type = request.getfixturevalue("db_type")
    if db_type not in LOCAL:
        pytest.skip(f"برای «{db_type}» هنوز داده‌ی آزمایشی در tests/conformance/local.py نیست.")
    if config.settings.customer.db_type != db_type:
        pytest.skip(f"مشتری فعال از نوع «{config.settings.customer.db_type}» است؛ برای "
                    f"سنجیدن «{db_type}» RASAM_CUSTOMER را روی مشتری آن بگذارید.")
    agent = agent_for(db_type)
    try:
        agent.describe_schema()
    except Exception as error:  # noqa: BLE001 — هر شکستی یعنی دیتابیس بالا نیست
        pytest.skip(f"دیتابیس محلی «{db_type}» در دسترس نیست: {type(error).__name__}")
    return agent


@db_types
def test_the_row_cap_holds_even_against_queries_that_ask_for_everything(db_type, local, monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, max_rows=ROW_CAP))
    sizes = []
    for _, source, query in cases(db_type, "unbounded_query"):
        checked = local.validate_query(source, query)
        if checked.ok:
            sizes.append(len(local.execute(source, checked)))
    assert sizes and max(sizes) <= ROW_CAP, f"سقف {ROW_CAP} رد شد: {sizes}"
    assert max(sizes) == ROW_CAP, "آزمون بی‌معنی است: هیچ‌کدام به سقف نرسید، یعنی داده‌ی کافی نبود"


@db_types
def test_the_row_filter_cannot_be_escaped(db_type, local, monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, max_rows=50))
    local_data = LOCAL[db_type]
    field, value = local_data["filter_field"], local_data["filter_value"]
    row_filter = {field: value}
    leaked_without_filter = False
    returned_something = False

    for _, source, query in cases(db_type, "row_filter_bypass"):
        unfiltered = local.validate_query(source, query)
        if unfiltered.ok:
            leaked_without_filter |= any(
                row.get(field) != value for row in local.execute(source, unfiltered))

        checked = local.validate_query(source, query, row_filter=row_filter)
        if not checked.ok:
            continue
        rows = local.execute(source, checked)
        returned_something |= bool(rows)  # حمله‌ی «مقدار دیگر» درست است که خالی بماند
        assert all(row.get(field) == value for row in rows), f"ردیف بیرون از شرط برگشت: {query}"

    assert returned_something, "آزمون بی‌معنی است: با شرط هیچ حمله‌ای ردیفی برنگرداند"
    assert leaked_without_filter, (
        "آزمون بی‌معنی است: بدون شرط هم ردیف بیرون از آن برنگشت، پس معلوم نیست شرط کاری کرده باشد")
