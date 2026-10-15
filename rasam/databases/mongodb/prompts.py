"""پرامپت ساختن کوئری MongoDB.

این پرامپت به زبان کوئری وابسته است، پس در پوشه‌ی مونگو می‌نشیند. MySQL پرامپت
خودش را در پوشه‌ی خودش دارد؛ آنچه به زبان ربط ندارد در `databases/prompt_parts.py`
مشترک است، و پرامپت خلاصه و نمودار در `rasam/core/prompts.py`.

متن پرامپت انگلیسی است چون به مدل می‌رود.
"""

from __future__ import annotations

import json
from typing import Any

from rasam import config
from rasam.core import knowledge
from rasam.core.prompts import QUESTION_TAG, wrap_untrusted
from rasam.databases.mongodb import guard
from rasam.databases.prompt_parts import (
    CHART_REQUEST, FAILURE_TEMPLATE, MAX_ERROR_CHARS, security_rules)

# فهرست‌ها از `guard.py` نقل می‌شوند، نه دوباره نوشته. گارد مرجع است؛ اگر
# پرامپت فهرست جداگانه‌ای داشته باشد، روزی از هم دور می‌افتند و مدل چیزی
# می‌سازد که گارد ردش می‌کند — بدون اینکه بفهمد چرا (تصمیم ۴۳). قاعده‌ی ۲ مخصوص مونگوست؛
# پنج قاعده‌ی دیگر مشترک‌اند (`prompt_parts.py`).
SECURITY_RULES = security_rules(
    "Produce exactly ONE read-only aggregation pipeline as a JSON array. Never use "
    f"{', '.join(sorted(guard.FORBIDDEN))}. Only these stages are allowed: "
    f"{', '.join(sorted(guard.ALLOWED_STAGES))}."
)

_TEMPLATE = """You turn Persian questions about a MongoDB database into aggregation pipelines.

===Database schema
{schema}

===Domain knowledge
{documentation}

===Worked examples
{examples}

{rules}

===Output format
On success, reply with ONLY a JSON object, nothing else:
{{"collection": "<one of: {collections}>", "pipeline": [<stages>]}}

Otherwise, per rule 5, reply with one short Persian sentence.

===Question
{question}"""

def format_example(example: dict) -> str:
    """یک نمونه‌ی `{question, why, source, query}` به متنی که مدل باید تقلید کند.

    قالب خروجی همان قالب پاسخ مدل است (`collection` و `pipeline`)، چون مدل از
    روی نمونه یاد می‌گیرد چه بنویسد. `why` هم می‌آید: مدل از دیدن *دلیل*، الگو
    را بهتر به سوال تازه تعمیم می‌دهد تا از دیدن کوئریِ تنها.
    """
    why = f"\n# {example['why'].strip()}" if example.get("why") else ""
    answer = {"collection": example["source"], "pipeline": example["query"]}
    return f"Q: {example['question']}{why}\nA: {json.dumps(answer, ensure_ascii=False)}"


def build_query_prompt(schema: str, question: str, collections: set[str],
                       failure: tuple[Any, str] | None = None,
                       want_chart: bool = False,
                       documentation: str | None = None,
                       examples: str | None = None) -> str:
    """پرامپت تولید کوئری: ساختار دیتابیس + قواعد امنیتی + سوال محصورشده.

    نام کالکشن‌های مجاز صریحاً در پرامپت می‌آید تا مدل از فهرست بیرون نزند.
    این جایگزین گارد نیست — گارد باز هم مستقل بررسی می‌کند — فقط احتمال یک
    رفت‌وبرگشت بی‌فایده را کم می‌کند.

    `failure` فقط در تلاش ترمیم داده می‌شود: (کوئری ردشده، دلیل رد). همان
    پرامپت با یک بخش اضافه ساخته می‌شود تا مدل دقیقاً بداند چه چیزی و چرا
    قبول نشد، بدون اینکه schema و نمونه‌ها دوباره تکرار شوند.
    """
    built = _TEMPLATE.format(
        schema=schema,
        documentation=documentation if documentation is not None else knowledge.documentation_text(),
        examples=examples if examples is not None else knowledge.examples_text(format_example),
        rules=SECURITY_RULES,
        collections=", ".join(sorted(collections)),
        question=wrap_untrusted(question, QUESTION_TAG),
    )
    if want_chart:
        built += CHART_REQUEST
    if failure is None:
        return built
    pipeline, reason = failure
    return built + FAILURE_TEMPLATE.format(
        query=json.dumps(pipeline, ensure_ascii=False)[:config.settings.max_result_chars],
        reason=reason[:MAX_ERROR_CHARS],
    )
