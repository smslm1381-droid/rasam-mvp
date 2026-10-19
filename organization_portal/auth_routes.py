"""مسیرهای ورود فقط نتیجهٔ سرویس حساب را نمایش می‌دهند."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from organization_portal import http, invitations, permissions
from organization_portal.models import InvitationAccept, Login, PasswordChange


def routes():
    router = APIRouter(prefix="/api")

    @router.get("/auth/status")
    def status(request: Request):
        user = http.current(request, required=False)
        orgs = permissions.organizations(request.app.state.store, user) if user else []
        return {"user": user, "organizations": orgs, "csrf": http.csrf(request) if user else None,
                "trial": True, "demo": bool(getattr(request.app.state.connections.engine, "demo", False)),
                "quota_policy": request.app.state.settings.quota_policy}

    @router.post("/auth/login")
    def login(request: Request, body: Login):
        settings = request.app.state.settings
        address = request.client.host if settings.local else request.headers.get("X-Rasam-Client-IP", "unknown")
        token = request.app.state.accounts.login(body.email, body.password.get_secret_value(), address)
        response = JSONResponse({"ok": True})
        response.set_cookie(settings.cookie, token, httponly=True, secure=not settings.local,
                            samesite="strict", max_age=8 * 3600, path="/")
        return response

    @router.post("/auth/logout")
    def logout(request: Request):
        http.current(request)
        request.app.state.accounts.logout(http.token(request))
        response = JSONResponse({"ok": True})
        response.delete_cookie(request.app.state.settings.cookie, path="/", secure=not request.app.state.settings.local, httponly=True)
        return response

    router.include_router(account_changes())
    return router


def account_changes():
    router = APIRouter()

    @router.post("/auth/password")
    def change_password(request: Request, body: PasswordChange):
        user = http.current(request)
        request.app.state.accounts.change_password(user, body.old.get_secret_value(), body.new.get_secret_value())
        response = JSONResponse({"ok": True, "message": "رمز تغییر کرد؛ همهٔ دستگاه‌ها باید دوباره وارد شوند."})
        response.delete_cookie(request.app.state.settings.cookie, path="/", secure=not request.app.state.settings.local, httponly=True)
        return response

    @router.get("/invitations/{invitation_token}")
    def invitation(request: Request, invitation_token: str):
        row, existing = invitations.details(request.app.state.store, invitation_token)
        return {"email": row["email"], "organization": row["org_name"], "existing_account": existing}

    @router.post("/invitations/accept")
    def accept(request: Request, body: InvitationAccept):
        user = http.current(request, required=False)
        return invitations.accept(request.app.state.store, body.token.get_secret_value(), body.name,
                                  body.password.get_secret_value(), user)

    return router
