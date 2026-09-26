"""خط فرمان رصام — یک سوال بپرس، جواب بگیر.

این فایل **هیچ منطقی ندارد** (قاعده‌ی امنیتی ۴). فقط `Answer` را می‌گیرد و
تمیز چاپ می‌کند. وقتی در قدم ۱۳ API بیاید، لایه‌ی نمایش عوض می‌شود بدون
اینکه رفتار برنامه ذره‌ای فرق کند.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rasam import config
from rasam.core import exporting
from rasam.core.graph import Answer, answer


def _cell(value) -> str:
    """خانه‌ی خالی، خالی چاپ می‌شود — نه کلمه‌ی `None`."""
    return "" if value is None else str(value)


def _visible_columns(rows: list[dict]) -> list[str]:
    """ستون‌هایی که ارزش نشان‌دادن دارند.

    ستون‌ها از *همه‌ی* ردیف‌ها جمع می‌شوند، نه فقط اولی: در مونگو داکیومنت‌ها
    لزوماً فیلد یکسان ندارند.

    ستونی که در تمام ردیف‌ها خالی است حذف می‌شود. علت واقعی‌اش `_id` است:
    نتیجه‌ی `$group: {_id: null}` همیشه یک ستون `_id` با مقدار `None` دارد که
    جواب نیست، فقط کلید گروه است. این حذف *فقط در نمایش* است — ردیف‌های خودِ
    `Answer` و خروجی CSV و API دست‌نخورده می‌مانند، چون آنجا مصرف‌کننده برنامه
    است نه چشم آدم.
    """
    columns = list(dict.fromkeys(key for row in rows for key in row))
    return [c for c in columns if any(row.get(c) is not None for row in rows)] or columns


def _render_rows(rows: list[dict]) -> str:
    """جدول نتیجه به‌صورت متن ساده، با ستون‌های هم‌عرض."""
    if not rows:
        return "کوئری اجرا شد ولی هیچ ردیفی برنگشت."

    columns = _visible_columns(rows)
    widths = {c: max(len(str(c)), *(len(_cell(r.get(c))) for r in rows)) for c in columns}
    header = "  ".join(str(c).ljust(widths[c]) for c in columns)
    lines = [header, "─" * len(header)]
    lines += ["  ".join(_cell(r.get(c)).ljust(widths[c]) for c in columns) for r in rows]
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
    """ذخیره‌ی نتیجه، اگر پروفایل مشتری این خروجی را داشته باشد.

    قابلیت‌های `export_csv` و `export_excel` در پروفایل نوشته می‌شوند؛ تا امروز
    هیچ‌کس نگاهشان نمی‌کرد و هر مشتری هر دو خروجی را می‌گرفت. کانفیگی که اثر
    ندارد بدتر از نبودنش است.
    """
    for path, kind, write in ((csv_path, "csv", exporting.write_csv),
                              (excel_path, "excel", exporting.write_excel)):
        if not path:
            continue
        if not exporting.is_enabled(kind):
            print(f"خروجی {kind} برای مشتری «{config.settings.customer.name}» فعال نیست.")
            continue
        write(result.rows, path)
        print(f"نتیجه در {path} ذخیره شد.")


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
