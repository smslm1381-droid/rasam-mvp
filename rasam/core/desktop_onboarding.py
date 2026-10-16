"""انتخاب داده و ساخت پروفایل رومیزی؛ اتصال نویسنده هرگز فعال نمی‌شود."""

from uuid import uuid4
from rasam import config, customer, vault, desktop_preferences
from rasam.core import onboarding, readiness, activation
from rasam.databases import registry
from rasam.errors import UserFacingError


def pending_agent(pending):
    if pending is None:
        raise UserFacingError("ابتدا اتصال را با موفقیت آزمایش کنید.")
    secret = vault.read_secret(pending["connection_env"])
    if not secret.ok or not secret.value:
        raise UserFacingError("اطلاعات اتصال در انبار امن در دسترس نیست؛ دوباره اتصال را آزمایش کنید.")
    return registry.AGENTS[pending["db_type"]](connection_uri=secret.value, database=pending["database"])


def inspect(pending):
    try:
        agent = pending_agent(pending)
        access = agent.check_read_only()
        if not access.read_only:
            return {"ok": False, "category": "read_only", "message": "این اتصال اجازهٔ نوشتن دارد؛ ادامه ممکن نیست.",
                    "script": agent.read_only_user_script(pending["database"])}
        return {"ok": True, "sources": [{"name": name, "sensitive": bool(onboarding.SENSITIVE_NAME.search(name))}
                                        for name in agent.list_sources()]}
    except UserFacingError as error:
        return {"ok": False, "message": str(error)}
    except Exception:
        return {"ok": False, "message": "خواندن منابع یا بررسی دسترسی‌ها ناموفق بود؛ اتصال را دوباره آزمایش کنید."}


def check_selection(name, sources, confirmed, pending):
    if not onboarding.NAME_RE.fullmatch(name) or len(name) > 64:
        raise UserFacingError("نام مشتری باید با حرف کوچک لاتین شروع شود و فقط حرف، عدد و خط تیره داشته باشد.")
    if (config.CUSTOMERS_DIR / name).exists():
        raise UserFacingError("این نام مشتری از قبل وجود دارد؛ نام دیگری انتخاب کنید.")
    inspected = inspect(pending)
    if not inspected["ok"]:
        return inspected
    available = {item["name"] for item in inspected["sources"]}
    selected = set(sources)
    if not selected or not selected <= available:
        raise UserFacingError("دست‌کم یک منبع موجود را انتخاب کنید.")
    sensitive = {item for item in selected if onboarding.SENSITIVE_NAME.search(item)}
    if not sensitive <= set(confirmed):
        raise UserFacingError("انتخاب منابع حساس به تأیید جداگانه نیاز دارد.")
    return {"ok": True}


def desktop_checks(name):
    checks = readiness.run_checks(name)
    optional = {"دانش دامنه کامل است", f"دست‌کم {readiness.MIN_GOLDEN_QUESTIONS} سوال طلایی"}
    return [display_check(item, optional) for item in checks]


def display_check(item, optional):
    labels = {
        "پروفایل معتبر و بدون راز": ("تنظیمات اتصال", "تنظیمات معتبر است."),
        "متغیر اتصال و برقراری اتصال": ("اتصال دیتابیس", "اتصال برقرار است."),
        "دانش دامنه کامل است": ("آموزش معنی داده‌ها", "برای دقت بیشتر، معنی ستون‌ها و نکته‌های داده را در آموزش رصام تکمیل کنید."),
        f"دست‌کم {readiness.MIN_GOLDEN_QUESTIONS} سوال طلایی": ("پرسش‌های ارزیابی", "اختیاری: پشتیبانی می‌تواند پرسش‌هایی برای بررسی دقت ثبت کند."),
    }
    name, detail = labels.get(item.name, (item.name, item.detail))
    if not item.ok and item.name not in optional:
        detail = "این بخش آماده نیست؛ اتصال را دوباره آزمایش کنید یا با پشتیبانی تماس بگیرید."
    return {"name": name, "detail": detail,
            "status": "ok" if item.ok else "warning" if item.name in optional else "error"}


def finish(pending, name, sources, confirmed):
    secret_name = None
    try:
        checked = check_selection(name, sources, confirmed, pending)
        if not checked["ok"]:
            return checked
        secret_name = "CUSTOMER_DB_" + uuid4().hex.upper()
        secret = vault.read_secret(pending["connection_env"])
        saved = vault.write_secret(secret_name, secret.value)
        if not saved.ok:
            raise UserFacingError(saved.error)
        agent = pending_agent(pending)
        folder = onboarding._write_customer(name, pending["db_type"], secret_name,
                                            pending["database"], sorted(set(sources)), agent)
        activation.activate(name)
        desktop_preferences.write_customer(config.DATA_HOME, name)
        vault.delete_secret(pending["connection_env"])
        return {"ok": True, "customer": name, "checks": desktop_checks(name)}
    except UserFacingError as error:
        message = str(error)
    except Exception:
        message = "ساخت پروفایل کامل نشد؛ فضای دیسک و دسترسی انبار امن را بررسی کنید."
    if secret_name is not None and not (config.CUSTOMERS_DIR / name).exists():
        vault.delete_secret(secret_name)
    return {"ok": False, "message": message}
