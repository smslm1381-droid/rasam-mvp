"""خط فرمان رصام — یک سوال بپرس، جواب بگیر.

این فایل **هیچ منطقی ندارد** (قاعده‌ی امنیتی ۴). فقط `Answer` را می‌گیرد و
تمیز چاپ می‌کند. وقتی در قدم ۱۳ API بیاید، لایه‌ی نمایش عوض می‌شود بدون
اینکه رفتار برنامه ذره‌ای فرق کند.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import exporting
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="پرسیدن سوال از رصام")
    parser.add_argument("question", nargs="*", help="سوال فارسی")
    parser.add_argument("--query", action="store_true", help="نمایش کوئری")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--csv", type=Path, metavar="PATH", help="ذخیره‌ی نتیجه به CSV")
    output.add_argument("--excel", type=Path, metavar="PATH", help="ذخیره‌ی نتیجه به Excel")
    return parser


def _export(result: Answer, csv_path: Path | None, excel_path: Path | None) -> None:
    if csv_path:
        exporting.write_csv(result.rows, csv_path)
        print(f"نتیجه در {csv_path} ذخیره شد.")
    if excel_path:
        exporting.write_excel(result.rows, excel_path)
        print(f"نتیجه در {excel_path} ذخیره شد.")


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    question = " ".join(args.question)

    result = answer(question)
    print(render(result, show_query=args.query))
    if not result.error and not result.message:
        _export(result, args.csv, args.excel)
    return 1 if result.error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
