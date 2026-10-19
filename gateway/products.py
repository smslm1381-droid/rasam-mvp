"""پلن فروش از دورهٔ اعتبار جداست؛ قیمت و مدل فقط با اختیار مدیر تغییر می‌کنند."""

import json
import re
import time

from gateway.licenses import plain

FIELDS = {"title", "description", "model", "daily_limit", "monthly_price", "yearly_price", "published"}
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:\-]{0,199}")


def validate(body):
    if not isinstance(body, dict) or set(body) != FIELDS:
        raise ValueError("فیلدهای پلن کامل نیستند.")
    for key, maximum in [("title", 80), ("description", 300), ("model", 200)]:
        if not isinstance(body[key], str) or len(body[key]) > maximum:
            raise ValueError("متن پلن بیش از حد بلند یا نامعتبر است.")
    clean = {**body, "title": body["title"].strip(), "model": body["model"].strip()}
    if not clean["title"] or type(clean["published"]) is not bool:
        raise ValueError("نام یا وضعیت انتشار پلن معتبر نیست.")
    if clean["model"] and not MODEL.fullmatch(clean["model"]):
        raise ValueError("شناسهٔ مدل معتبر نیست؛ شناسهٔ سرویس فعلی را وارد کنید.")
    if type(clean["daily_limit"]) is not int or not 1 <= clean["daily_limit"] <= 100000:
        raise ValueError("سهمیهٔ روزانه باید بین ۱ و ۱۰۰۰۰۰ باشد.")
    for name in ["monthly_price", "yearly_price"]:
        price = clean[name]
        if price is not None and (type(price) is not int or not 0 <= price <= 10**12):
            raise ValueError("قیمت باید عدد صحیح نامنفی به تومان باشد؛ خالی یعنی عرضه نمی‌شود.")
    if clean["published"] and (not clean["model"] or all(clean[k] is None for k in ["monthly_price", "yearly_price"])):
        raise ValueError("برای انتشار، مدل و قیمت حداقل یک دوره را تکمیل کنید.")
    return clean


async def listing(db, public=False):
    where = " WHERE published=1 AND model<>'' AND (monthly_price IS NOT NULL OR yearly_price IS NOT NULL)" if public else ""
    result = plain(await db.prepare("SELECT * FROM products" + where + " ORDER BY position").all())
    return [{key: row[key] for key in ["id", *sorted(FIELDS), "updated_at"]} for row in result.get("results", [])]


async def read(db, identifier):
    return plain(await db.prepare("SELECT * FROM products WHERE id=?").bind(identifier).first())


async def save(db, identifier, body, actor):
    clean = validate(body)
    if await read(db, identifier) is None:
        return None
    now = int(time.time())
    columns = sorted(FIELDS)
    update = "UPDATE products SET " + ",".join(name + "=?" for name in columns) + ",updated_at=? WHERE id=?"
    stored = {**clean, "published": int(clean["published"])}
    await db.batch([db.prepare(update).bind(*(stored[name] for name in columns), now, identifier),
                   db.prepare("INSERT INTO product_changes(product_id,actor,created_at,details) VALUES (?,?,?,?)")
                   .bind(identifier, actor, now, json.dumps(clean, ensure_ascii=False))])
    return await read(db, identifier)
