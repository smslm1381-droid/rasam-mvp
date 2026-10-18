"""سنجه‌ی کیفیت: از سوالات طلایی، چند درصد درست جواب گرفتند.

بدون این عدد، هر تغییری در پرامپت یا دانش دامنه یک قمار است. با آن، می‌شود
گفت «این تغییر درصد را از ۸۰ به ۹۳ برد» یا «بدترش کرد، برگردانش».

مقایسه دقیق و عددی است، نه با مدل (قاعده‌ی سادگی قدم ۸): اگر عدد برابر بود
قبول، وگرنه رد. ارزیابی با مدل هم گران است هم خودش خطا دارد.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rasam import config, console  # noqa: E402
from rasam.core import graph  # noqa: E402
from rasam.core.answer import Answer  # noqa: E402

# سوالات طلایی مال هر مشتری است — جواب‌هایشان از داده‌ی همان مشتری آمده.
QUESTIONS_FILE = config.settings.customer.directory / "golden_questions.yaml"

# فاصله، فشار لحظه‌ای درخواست‌ها را کم می‌کند؛ محدودیت روزانه و محدودیت خود
# ارائه‌دهنده مستقل‌اند و با این مکث برداشته نمی‌شوند.
DEFAULT_PAUSE = 20.0

DEFAULT_TOLERANCE = 0.01


def _numbers(row: dict) -> dict[str, float]:
    """مقادیر عددی یک ردیف.

    `_id` رد می‌شود چون در `$group` تک‌گروهی مقدارش `None` است و در
    گروه‌بندی‌ها کلید است نه جواب.
    """
    return {key: float(value) for key, value in row.items()
            if key != "_id" and isinstance(value, (int, float))
            and not isinstance(value, bool)}


def _has_answer(row: dict, expect: dict) -> tuple[bool, str]:
    """آیا عددِ خواسته‌شده در این ردیف هست؟

    مدل نام ستون را خودش انتخاب می‌کند (`avg_temp`، `average_temperature`، …)
    پس نمی‌شود روی نام حساب کرد و **هر** مقدار عددی ردیف پذیرفته می‌شود.

    این ساده‌لوحانه نیست، عمدی است: اولین نسخه «اولین عدد ردیف» را می‌گرفت و
    سوال «آخرین توان اکتیو» را غلط اعلام می‌کرد، چون کوئری درست `timestamp` را
    هم برمی‌گرداند و آن اول می‌آمد. سنجه‌ای که کوئری درست را رد کند بی‌فایده
    است. اگر ابهام ماند، سوال می‌تواند `field` را صریح بگوید.
    """
    numbers = _numbers(row)
    if not numbers:
        return False, f"عددی برنگشت: {str(row)[:40]}"

    want = float(expect["value"])
    tolerance = float(expect.get("tolerance", DEFAULT_TOLERANCE))
    if field := expect.get("field"):
        got = numbers.get(field)
        if got is None:
            return False, f"فیلد {field} در نتیجه نبود: {sorted(numbers)}"
        return abs(got - want) <= tolerance, f"{got:g}"

    for value in numbers.values():
        if abs(value - want) <= tolerance:
            return True, f"{value:g}"
    return False, f"{', '.join(f'{v:g}' for v in numbers.values())} به‌جای {want:g}"


def grade(expect: dict, answer: Answer) -> tuple[str, str]:
    """یک سوال را نمره می‌دهد. خروجی: (وضعیت، توضیح کوتاه).

    سه وضعیت، و تفکیکشان برای صداقتِ عدد حیاتی است: اگر خطای سرویس را «جواب
    غلط» بشماریم، درصد دروغ می‌گوید. قاعده‌ی تفکیک این است که اگر مدل کوئری
    ساخته باشد، قضاوت درباره‌اش منصفانه است؛ اگر اصلاً کوئری‌ای نرسیده، چیزی
    برای قضاوت نداریم.
    """
    if answer.error and answer.query is None:
        return "skipped", answer.error[:60]
    if answer.error:
        return "wrong", answer.error[:60]

    if expect.get("message"):
        return ("ok", answer.message[:50]) if answer.message else ("wrong", "کوئری ساخت")
    if answer.message:
        return "wrong", f"جواب نداد: {answer.message[:40]}"

    if expect.get("empty"):
        return ("ok", "خالی") if not answer.rows else ("wrong", f"{len(answer.rows)} ردیف")
    if not answer.rows:
        return "wrong", "نتیجه‌ی خالی"

    matched, note = _has_answer(answer.rows[0], expect)
    return ("ok" if matched else "wrong"), note


def run(questions: list[dict], pause: float, answerer=None) -> list[tuple[dict, str, str]]:
    """هر سوال را می‌پرسد و نمره می‌دهد. خروجی: (سوال، وضعیت، توضیح) برای هرکدام."""
    marks = {"ok": "✅", "wrong": "❌", "skipped": "⚠️ "}
    results = []
    answerer = answerer or graph.answer

    for index, item in enumerate(questions, start=1):
        status, note = grade(item["expect"], answerer(item["question"]))
        results.append((item, status, note))
        print(f"  {marks[status]} {index:>2}. {item['question'][:46]:<48} {note}")
        if status == "skipped":
            print("  سنجه ناقص ماند؛ پس از رفع خطای سرویس دوباره اجرا کنید.")
            break
        if index < len(questions):
            time.sleep(pause)
    return results


def report(results: list[tuple[dict, str, str]]) -> int:
    """اجرای ناقص هم ناموفق است؛ قطع سرویس نباید گزارش سبز بسازد."""
    correct = sum(1 for _, status, _ in results if status == "ok")
    wrong = [(item, note) for item, status, note in results if status == "wrong"]
    skipped = sum(1 for _, status, _ in results if status == "skipped")
    judged = correct + len(wrong)

    print()
    if judged:
        print(f"  نرخ جواب درست: {correct / judged * 100:.0f}٪"
              f"  ({correct} از {judged} سوال قابل‌سنجش)")
    else:
        print("  هیچ سوالی سنجیده نشد.")
    if skipped:
        print(f"  ⚠️  {skipped} سوال به‌خاطر خطای سرویس سنجیده نشد و در درصد بالا نیامده.")

    if wrong:
        print("\n  شکست‌خورده‌ها:")
        for item, note in wrong:
            print(f"    • {item['question']}\n      → {note}")
            if item.get("trap"):
                print(f"      تله: {item['trap']}")
    return len(wrong) + skipped


def parse_args():
    parser = argparse.ArgumentParser(description="سنجش نرخ جواب درست روی سوالات طلایی")
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE,
                        help="فاصلهٔ بین سؤال‌ها به ثانیه؛ سقف روزانه جداست")
    parser.add_argument("--only", default="",
                        help="فقط سوالاتی که این متن در آن‌ها هست")
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--api-url", help="نشانی API؛ کلید از تنظیمات محیط خوانده می‌شود")
    transport.add_argument("--desktop-home", type=Path, help="پوشهٔ دادهٔ نسخهٔ رومیزیِ باز")
    return parser.parse_args()


def select_answerer(args):
    from scripts.evaluate_http import http_answerer, desktop_answerer
    if args.desktop_home:
        return desktop_answerer(args.desktop_home)
    if args.api_url:
        if not config.settings.api_key:
            raise ValueError("برای سنجهٔ API مقدار RASAM_API_KEY لازم است.")
        return http_answerer(args.api_url, {"X-API-Key": config.settings.api_key})
    return graph.answer


def main() -> int:
    console.use_utf8()
    args = parse_args()
    try:
        answerer = select_answerer(args)
    except ValueError as error:
        print(error)
        return 1

    questions = yaml.safe_load(console.read_text(QUESTIONS_FILE))
    if args.only:
        questions = [q for q in questions if args.only in q["question"]]
    if not questions:
        print("هیچ سوالی با این فیلتر پیدا نشد.")
        return 1

    print(f"سنجش {len(questions)} سوال، با {args.pause:g} ثانیه فاصله:\n")
    return 0 if report(run(questions, args.pause, answerer)) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
