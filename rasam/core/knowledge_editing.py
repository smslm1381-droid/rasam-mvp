"""ویرایش دانش و ثبت نمونهٔ تأییدشده؛ ورودی مدل دوباره از گارد می‌گذرد."""

import json
import sys
from uuid import uuid4
import yaml

from rasam import config, console
from rasam.core import knowledge
from rasam.databases import registry
from rasam.errors import UserFacingError


SEPARATOR = " — "


def field_catalog():
    if config.settings is None:
        raise UserFacingError("ابتدا اتصال دیتابیس را تنظیم کنید.")
    agent = registry.get_agent()
    catalog = {}
    for source in sorted(config.settings.allowed_sources):
        for name in agent.list_fields(source):
            catalog.setdefault(name, []).append(source)
    return catalog


def editor_state():
    try:
        notes = knowledge.field_notes()
        fields = []
        for name, sources in field_catalog().items():
            text = notes.get(name, "")
            label, separator, note = text.partition(SEPARATOR)
            fields.append({"name": name, "sources": sources,
                           "label": label if separator else "", "note": note if separator else text})
        return {"ok": True, "customer": config.settings.customer.name,
                "fields": fields, "documentation": knowledge.documentation_text()}
    except UserFacingError as error:
        return {"ok": False, "message": str(error)}
    except Exception:
        return {"ok": False, "message": "خواندن معنی ستون‌ها ممکن نشد؛ اتصال و فایل دانش را بررسی کنید."}


def atomic_text(path, text):
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def rebuild():
    knowledge.documentation_text.cache_clear()
    knowledge.field_notes.cache_clear()
    knowledge.examples.cache_clear()
    registry.reset_caches()
    graph = sys.modules.get("rasam.core.graph")
    if graph is not None:
        graph._knowledge_store.cache_clear()
    profile = config.settings.customer
    schema = registry.get_agent().describe_schema()
    knowledge.KnowledgeStore(profile.name, config.CHROMA_DIR).rebuild(schema, profile.directory)


def save(fields, documentation, customer_name):
    try:
        if config.settings is None or customer_name != config.settings.customer.name:
            raise UserFacingError("اتصال فعال عوض شده است؛ صفحهٔ آموزش را دوباره باز کنید.")
        available = field_catalog()
        if len(documentation) > 100000:
            raise UserFacingError("متن مستندات بیش از اندازه بلند است؛ آن را کوتاه‌تر کنید.")
        notes = dict(knowledge.field_notes())
        names = [item["name"] for item in fields]
        if len(names) != len(set(names)) or not set(names) <= available.keys():
            raise UserFacingError("فهرست ستون‌ها معتبر نیست؛ صفحهٔ آموزش را دوباره باز کنید.")
        for item in fields:
            label, note = item["label"].strip(), item["note"].strip()
            if len(label) > 120 or len(note) > 2000:
                raise UserFacingError("نام فارسی یا توضیح ستون بیش از اندازه بلند است.")
            text = label + SEPARATOR + note if label else note
            if text:
                notes[item["name"]] = text
            else:
                notes.pop(item["name"], None)
        folder = config.settings.customer.directory
        atomic_text(folder / knowledge.FIELD_NOTES_FILE, yaml.safe_dump(notes, allow_unicode=True, sort_keys=True))
        atomic_text(folder / knowledge.DOCUMENTATION_FILE, documentation)
        rebuild()
        return {"ok": True, "message": "معنی داده‌ها ذخیره شد و آموزش رصام به‌روز شد."}
    except UserFacingError as error:
        return {"ok": False, "message": str(error)}
    except Exception:
        return {"ok": False, "message": "ذخیره یا به‌روزرسانی آموزش کامل نشد؛ اتصال و دسترسی پوشهٔ داده را بررسی کنید."}


def confirm_answer(answer):
    try:
        if answer is None or answer.error or answer.message or not answer.source or answer.query is None:
            raise UserFacingError("این پاسخ برای نمونهٔ آموزشی مناسب نیست؛ دوباره سؤال را بپرسید.")
        checked = registry.get_agent().validate_query(answer.source, answer.query)
        if not checked.ok:
            raise UserFacingError("کوئری این پاسخ از بررسی ایمنی نگذشت و ذخیره نشد.")
        example = {"question": answer.question, "why": "", "source": answer.source, "query": checked.query}
        examples = list(knowledge.examples())
        if any(all(item.get(key) == example[key] for key in ("question", "source", "query")) for item in examples):
            return {"ok": True, "message": "این نمونه قبلاً ثبت شده است."}
        examples.append(example)
        atomic_text(config.settings.customer.directory / knowledge.EXAMPLES_FILE,
                    yaml.safe_dump(examples, allow_unicode=True, sort_keys=False))
        rebuild()
        return {"ok": True, "message": "پاسخ تأییدشده به نمونه‌های آموزشی اضافه شد."}
    except UserFacingError as error:
        return {"ok": False, "message": str(error)}
    except Exception:
        return {"ok": False, "message": "ثبت نمونه کامل نشد؛ اتصال و پوشهٔ داده را بررسی کنید."}


def count_negative(answer):
    if answer is None or config.settings is None:
        return {"ok": False, "message": "این پاسخ دیگر در دسترس نیست."}
    try:
        path = config.settings.customer.directory / "feedback.json"
        data = json.loads(console.read_text(path)) if path.exists() else {"negative": 0}
        count = data.get("negative", 0)
        if type(count) is not int or count < 0:
            raise ValueError("invalid counter")
        atomic_text(path, json.dumps({"negative": count + 1}))
        return {"ok": True, "message": "بازخورد شما ثبت شد؛ متن پرسش و پاسخ ذخیره نشد."}
    except Exception:
        return {"ok": False, "message": "ثبت بازخورد ممکن نشد؛ دسترسی پوشهٔ داده را بررسی کنید."}
