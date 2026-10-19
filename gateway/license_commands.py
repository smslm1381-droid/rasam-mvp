"""قواعد مشترک صدور و تغییر لایسنس برای خط فرمان و پنل."""

import re
import secrets
import time

from gateway import licenses


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


HASH = re.compile(r"^[a-f0-9]{64}$")


def issue(customer, plan, daily_limit=20, now=None, model=None, product_id=None):
    if (not isinstance(customer, str) or not customer.strip() or len(customer) > 200
            or type(daily_limit) is not int or not 1 <= daily_limit <= 100000):
        raise ValueError("نام مشتری یا سهمیه معتبر نیست.")
    if plan not in ("monthly", "yearly"):
        raise ValueError("پلن باید monthly یا yearly باشد.")
    if model is not None:
        from gateway.products import MODEL
        if not isinstance(model, str) or not MODEL.fullmatch(model):
            raise ValueError("شناسهٔ مدل معتبر نیست.")
    if product_id is not None and (not isinstance(product_id, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", product_id)):
        raise ValueError("شناسهٔ پلن معتبر نیست.")
    now = int(time.time()) if now is None else now
    key = "rasam_" + secrets.token_urlsafe(32)
    digest = licenses.token_hash(key)
    expires = now + (30 if plan == "monthly" else 365) * 86400
    columns = ["token_hash", "customer", "plan", "expires_at", "daily_limit"]
    values = [literal(digest), literal(customer.strip()), literal(plan), str(expires), str(daily_limit)]
    if model is not None:
        columns += ["model", "product_id"]
        values += [literal(model), literal(product_id) if product_id else "NULL"]
    sql = "INSERT INTO licenses(" + ", ".join(columns) + ") VALUES (" + ", ".join(values) + ");"
    return key, digest, expires, sql


def change(identifier, days=None, now=None):
    if not isinstance(identifier, str) or not HASH.fullmatch(identifier):
        raise ValueError("شناسهٔ لایسنس باید همان هش ۶۴حرفی فهرست باشد؛ کلید خام را اینجا ننویسید.")
    if days is None:
        return f"UPDATE licenses SET active = 0 WHERE token_hash = '{identifier}' RETURNING token_hash;"
    if type(days) is not int or not 1 <= days <= 3650:
        raise ValueError("تعداد روز تمدید باید بین ۱ و ۳۶۵۰ باشد.")
    now = int(time.time()) if now is None else now
    return (f"UPDATE licenses SET active = 1, expires_at = MAX(expires_at, {now}) + {days * 86400} "
            f"WHERE token_hash = '{identifier}' RETURNING token_hash;")


def quota(identifier, daily_limit):
    if not isinstance(identifier, str) or not HASH.fullmatch(identifier):
        raise ValueError("شناسهٔ لایسنس معتبر نیست.")
    if type(daily_limit) is not int or not 1 <= daily_limit <= 100000:
        raise ValueError("سهمیه باید عدد صحیح بین ۱ و ۱۰۰۰۰۰ باشد.")
    return (f"UPDATE licenses SET daily_limit = {daily_limit} WHERE token_hash = '{identifier}' "
            "RETURNING token_hash;")
