"""توکن هر اجرا و کنترل میزبان، دسترسی صفحه‌های دیگر و شبکه را می‌بندند."""

from __future__ import annotations

import secrets
import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; img-src 'self' data: blob:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
}


def reject(detail: str, status: int = 403):
    return JSONResponse({"detail": detail}, status_code=status, headers=SECURITY_HEADERS)


class LocalSecurity(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token
        self.cookie_name = "rasam-" + hashlib.sha256(token.encode()).hexdigest()[:16]

    async def dispatch(self, request, call_next):
        if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
            return reject("این برنامه فقط از همین کامپیوتر قابل استفاده است.")
        if request.url.hostname not in {"127.0.0.1", "localhost"}:
            return reject("نشانی درخواست معتبر نیست.")
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return reject("درخواست از صفحهٔ دیگری پذیرفته نمی‌شود.")
        if request.headers.get("sec-fetch-site") == "cross-site":
            return reject("درخواست از صفحهٔ دیگری پذیرفته نمی‌شود.")
        if not request.url.path.startswith("/static/"):
            supplied = request.headers.get("x-rasam-token", "")
            if request.url.path == "/":
                supplied = request.query_params.get("token") or supplied or request.cookies.get(self.cookie_name, "")
            if not secrets.compare_digest(supplied.encode(), self.token.encode()):
                return reject("دسترسی معتبر نیست؛ برنامه را دوباره باز کنید.", 401)
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if request.url.path == "/":
            response.set_cookie(self.cookie_name, self.token, httponly=True, samesite="strict")
        return response
