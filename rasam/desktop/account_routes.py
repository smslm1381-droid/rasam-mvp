"""ورود محلی جدا از لایسنس است؛ ایجاد حساب فقط پس از فعال‌سازی مجاز است."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr

COOKIE = "rasam_local_account"


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: SecretStr = Field(min_length=8, max_length=128)


def _session_response(account):
    response = JSONResponse({"ok": True})
    response.set_cookie(COOKIE, account.issue_session(), httponly=True, samesite="strict", path="/")
    return response


def routes(app):
    router = APIRouter(prefix="/auth")
    account = app.state.account

    @router.get("/status")
    def status(request: Request):
        return {**account.state(), "authenticated": account.authenticated(request.cookies.get(COOKIE, ""))}

    @router.post("/register")
    def register(body: Credentials):
        if not account.enabled:
            return JSONResponse({"ok": False, "detail": "حساب محلی مخصوص نسخهٔ رومیزی است."}, status_code=400)
        with app.state.session.lock:
            license_status = app.state.licensing.refresh()
            if not license_status.get("required") or not license_status.get("valid"):
                return JSONResponse({"ok": False, "detail": "ابتدا لایسنس معتبر را فعال کنید."}, status_code=403)
            result = account.register(body.username, body.password.get_secret_value())
        return _session_response(account) if result.ok else JSONResponse({"ok": False, "detail": result.reason}, status_code=409)

    @router.post("/login")
    def login(body: Credentials):
        result = account.login(body.username, body.password.get_secret_value())
        return _session_response(account) if result.ok else JSONResponse({"ok": False, "detail": result.reason}, status_code=401)

    @router.post("/logout")
    def logout(request: Request):
        account.logout(request.cookies.get(COOKIE, ""))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/")
        return response

    return router
