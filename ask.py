"""خط فرمان رصام — یک سوال بپرس، جواب بگیر.

این فایل **هیچ منطقی ندارد** (قاعده‌ی امنیتی ۴). فقط `Answer` را می‌گیرد و
تمیز چاپ می‌کند. وقتی در قدم ۱۳ API بیاید، لایه‌ی نمایش عوض می‌شود بدون
اینکه رفتار برنامه ذره‌ای فرق کند.
"""

from __future__ import annotations

import sys

from graph import Answer, answer


def _render_rows(rows: list[dict]) -> str:
    """جدول نتیجه به‌صورت متن ساده، با ستون‌های هم‌عرض."""
    if not rows:
        return "کوئری اجرا شد ولی هیچ ردیفی برنگشت."

    columns = list(rows[0])
    widths = {c: max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    header = "  ".join(str(c).ljust(widths[c]) for c in columns)
    lines = [header, "─" * len(header)]
    lines += ["  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns) for r in rows]
    return "\n".join(lines)


def render(result: Answer, show_query: bool) -> str:
    """`Answer` را به متن چاپ‌شدنی تبدیل می‌کند.

    سه حالت جدا از هم: خطا، جواب متنی مدل، و جدول نتیجه. حالت دوم خطا نیست —
    مدل فهمیده سوال از این داده قابل جواب نیست و همین را گفته.
    """
    if result.error:
        return f"خطا: {result.error}"
    if result.message:
        return result.message

    parts = []
    if result.summary:
        parts.append(result.summary)
    if show_query:
        parts.append(f"کالکشن: {result.collection}\nکوئری: {result.pipeline}")
    parts.append(_render_rows(result.rows))
    return "\n\n".join(parts)


def main(argv: list[str]) -> int:
    flags = {a for a in argv if a.startswith("--")}
    question = " ".join(a for a in argv if not a.startswith("--"))

    result = answer(question)
    print(render(result, show_query="--query" in flags))
    return 1 if result.error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
