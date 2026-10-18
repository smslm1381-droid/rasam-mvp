"""خواندن محدود درخواست و پاسخ خطای فارسی پنل."""

import json
from fastapi.responses import JSONResponse


def error(message, status=400):
    return JSONResponse({"ok": False, "message": message}, status_code=status)


async def read_body(request):
    if request.headers.get("Content-Type", "").split(";")[0] != "application/json":
        raise ValueError("درخواست باید JSON باشد.")
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > 4096:
            raise ValueError("متن درخواست بیش از حد بلند است.")
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError("درخواست معتبر نیست.")
    return body
