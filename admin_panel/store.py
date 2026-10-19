"""خواندن دادهٔ مدیریتی از همان D1 لایسنس؛ بدون متن پرسش یا راز مشتری."""

import time
from datetime import datetime, timezone

from gateway.licenses import plain


def public_row(row, now):
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    state = "revoked" if not row["active"] else "expired" if row["expires_at"] <= now else "active"
    return {"identifier": row["token_hash"], "customer": row["customer"], "plan": row["plan"],
            "expires_at": row["expires_at"], "daily_limit": row["daily_limit"], "status": state,
            "used_today": row["used"] if row["usage_day"] == day else 0,
            "model": row.get("model"), "product_id": row.get("product_id")}


async def listing(db, search="", status="all", page=1, now=None):
    now = int(time.time()) if now is None else now
    if not isinstance(search, str) or len(search) > 200 or type(page) is not int or not 1 <= page <= 100000:
        raise ValueError("جست‌وجو یا شمارهٔ صفحه معتبر نیست.")
    filters = {"all": "1 = 1", "active": "active = 1 AND expires_at > ?",
               "expired": "active = 1 AND expires_at <= ?", "revoked": "active = 0"}
    if status not in filters:
        raise ValueError("وضعیت انتخاب‌شده معتبر نیست.")
    condition = "instr(lower(customer), lower(?)) > 0 AND (" + filters[status] + ")"
    params = [search] + ([now] if status in {"active", "expired"} else [])
    total = plain(await db.prepare("SELECT COUNT(*) AS total FROM licenses WHERE " + condition).bind(*params).first())
    result = plain(await db.prepare("SELECT * FROM licenses WHERE " + condition + " ORDER BY customer, token_hash LIMIT 50 OFFSET ?")
                   .bind(*params, (page - 1) * 50).all())
    rows = [public_row(row, now) for row in result.get("results", [])]
    return {"licenses": rows, "total": total["total"], "page": page, "page_size": 50}
