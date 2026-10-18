"""پرامپت ساختن کوئری MySQL.

همان نقش `mongodb/prompts.py`، برای SQL. قواعد غیرمربوط به زبان از
`databases/prompt_parts.py` می‌آیند؛ آنچه اینجاست قاعده‌ی ۲ (چه کوئری‌ای و چه
ممنوعی)، قالب خروجی و قالب نمونه است. فهرست توابع مجاز و ممنوع از `guard.py` نقل
می‌شود، نه دوباره نوشته (تصمیم‌های ۴۳ و ۹۶).

متن پرامپت انگلیسی است چون به مدل می‌رود.
"""

from __future__ import annotations

import json
from typing import Any

from rasam import config
from rasam.core import knowledge
from rasam.core.prompts import QUESTION_TAG, wrap_untrusted
from rasam.databases.mysql import guard
from rasam.databases.prompt_parts import (
    CHART_REQUEST, FAILURE_TEMPLATE, MAX_ERROR_CHARS, security_rules, context_text)

SECURITY_RULES = security_rules(
    "Only when actual customer records are needed and the schema supports the request, "
    "produce exactly ONE read-only SQL statement: a single SELECT on a single table, "
    "with no semicolon. Never use JOIN, UNION, subqueries, WITH, window functions, "
    "INTO, FOR UPDATE, @variables, optimizer hints or comments. Never call "
    f"{', '.join(guard.FORBIDDEN_FUNCTIONS)}. "
    f"Only these functions are allowed: {', '.join(guard.FUNCTIONS_DISPLAY)}. "
    "Quote column and table names with backticks if they could be keywords."
)

_TEMPLATE = """You answer Persian questions, choosing in this same response between a
direct Persian answer and a read-only MySQL SELECT query. Follow rule 5:
the deciding factor is the need for actual customer records.

===Database schema
{schema}

===Domain knowledge
{documentation}

===Worked examples
{examples}

{rules}

===Output format
If actual customer records are needed and the supplied schema supports the request,
reply with ONLY this JSON object, nothing else:
{{"table": "<one of: {tables}>", "sql": "<one SELECT statement on that table>"}}

Otherwise, per rule 5, reply with short plain Persian text: either a direct answer
that needs no customer records, or a clear explanation of the missing customer data.

===Question
{question}"""


def format_example(example: dict) -> str:
    """یک نمونه‌ی `{question, why, source, query}` به متنی که مدل باید تقلید کند.

    قالب خروجی همان قالب پاسخ مدل است (`table` و `sql`)، چون مدل از روی نمونه یاد
    می‌گیرد چه بنویسد. `why` هم می‌آید: مدل از دیدن *دلیل*، الگو را بهتر تعمیم می‌دهد.
    """
    why = f"\n# {example['why'].strip()}" if example.get("why") else ""
    answer = {"table": example["source"], "sql": " ".join(str(example["query"]).split())}
    return f"Q: {example['question']}{why}\nA: {json.dumps(answer, ensure_ascii=False)}"


def build_query_prompt(schema: str, question: str, tables: set[str],
                       failure: tuple[Any, str] | None = None,
                       want_chart: bool = False,
                       documentation: str | None = None,
                       examples: str | None = None) -> str:
    """پرامپت تولید کوئری: ساختار دیتابیس + قواعد امنیتی + سوال محصورشده.

    نام جدول‌های مجاز صریحاً در پرامپت می‌آید تا مدل از فهرست بیرون نزند؛ این
    جایگزین گارد نیست، فقط احتمال یک رفت‌وبرگشت بی‌فایده را کم می‌کند. `failure`
    فقط در تلاش ترمیم می‌آید: (کوئری ردشده، دلیل رد).
    """
    built = _TEMPLATE.format(
        schema=context_text(schema, "SCHEMA_CONTEXT"),
        documentation=context_text(documentation if documentation is not None else knowledge.documentation_text(), "DOMAIN_CONTEXT"),
        examples=context_text(examples if examples is not None else knowledge.examples_text(format_example), "EXAMPLE_CONTEXT"),
        rules=SECURITY_RULES,
        tables=", ".join(sorted(tables)),
        question=wrap_untrusted(question, QUESTION_TAG),
    )
    if want_chart:
        built += CHART_REQUEST
    if failure is None:
        return built
    query, reason = failure
    return built + FAILURE_TEMPLATE.format(
        query=str(query)[:config.settings.max_result_chars],
        reason=reason[:MAX_ERROR_CHARS],
    )
