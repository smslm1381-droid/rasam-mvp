"""تماس فقط با نشانی پیکربندی‌شدهٔ سرور؛ پاسخ خطای سرویس بازتاب داده نمی‌شود."""

import asyncio
import json
from urllib.parse import urlsplit


async def chat(env, payload):
    from workers import fetch
    base_url = env.UPSTREAM_BASE_URL.rstrip("/")
    parts = urlsplit(base_url)
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost")):
        return None
    try:
        response = await asyncio.wait_for(fetch(base_url + "/chat/completions", method="POST",
            headers={"Authorization": "Bearer " + env.UPSTREAM_API_KEY, "Content-Type": "application/json"},
            body=json.dumps(payload)), timeout=90)
        if response.status != 200:
            return None
        text = await response.text()
        if len(text) > 2000000:
            return None
        result = json.loads(text)
        if not isinstance(result, dict) or not isinstance(result.get("choices"), list):
            return None
        return result
    except Exception:
        return None
