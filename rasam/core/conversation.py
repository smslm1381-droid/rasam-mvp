"""سلامِ تنها درخواست کوئری نیست؛ برای پاسخ به آن داده‌ای از مشتری لازم نداریم."""

import re
import unicodedata


def reply(question: str) -> str | None:
    text = unicodedata.normalize("NFKC", question).casefold()
    text = text.translate(str.maketrans({"ي": "ی", "ك": "ک", "\u200c": " "}))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = " ".join(re.sub(r"[^\w\s]", " ", text).split())
    # تطبیق کل پیام است؛ «سلام، میانگین دما چقدر است؟» باید به مسیر داده برود.
    if text in {"سلام", "سلام رصام", "سلام خوبی", "سلام وقت بخیر", "درود",
                "وقت بخیر", "صبح بخیر", "عصر بخیر", "hello", "hi"}:
        return "سلام! خوش آمدید. چه چیزی می‌خواهید دربارهٔ داده‌هایتان بدانید؟"
    if text in {"ممنون", "متشکرم", "سپاس", "خیلی ممنون", "thanks", "thank you"}:
        return "خواهش می‌کنم! اگر سؤال دیگری دربارهٔ داده‌ها دارید، بپرسید."
    if text in {"خداحافظ", "خدا حافظ", "فعلا", "bye", "goodbye"}:
        return "خدانگهدار! هر وقت سؤالی دربارهٔ داده‌ها داشتید، در خدمتم."
    return None
