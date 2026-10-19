"""وب‌اپ سازمانی؛ هستهٔ مدل و دیتابیس مشتری در فرایند جدا اجرا می‌شود."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from organization_portal import admin_routes, auth_routes, chat_routes, http
from organization_portal.auth import Accounts
from organization_portal.chats import Chats
from organization_portal.connections import Connections
from organization_portal.engine import Engine
from organization_portal.errors import PortalError
from organization_portal.settings import from_environment
from organization_portal.store import LocalStore, RemoteStore

PUBLIC = Path(__file__).with_name("public")
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
       "base-uri 'self'; form-action 'self'")


def create_app(settings=None, store=None, engine=None):
    settings = (settings or from_environment()).validate()
    store = store or (LocalStore(settings.home / "organizations.sqlite3") if settings.local
                      else RemoteStore(settings.storage_url, settings.storage_key))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.store = settings, store
    app.state.accounts = Accounts(store)
    app.state.connections = Connections(store, settings.key, engine or Engine(settings.local), settings.local)
    app.state.chats = Chats(store, app.state.connections, settings.quota_policy)
    for router in [auth_routes.routes(), admin_routes.routes(), chat_routes.routes(), chat_routes.managed_routes()]:
        app.include_router(router)
    app.add_exception_handler(PortalError, portal_error)
    app.add_exception_handler(RequestValidationError, invalid_input)
    app.add_exception_handler(Exception, unexpected_error)
    app.middleware("http")(boundary)
    if PUBLIC.is_dir():
        app.mount("/static", StaticFiles(directory=PUBLIC / "static"), name="static")
        app.add_api_route("/", index, methods=["GET"])
    app.add_api_route("/health", health, methods=["GET"])
    return app


async def boundary(request: Request, call_next):
    try:
        if request.url.path.startswith("/api/"):
            http.protect(request)
            if int(request.headers.get("Content-Length", "0")) > 2 * 1024 * 1024:
                raise PortalError("درخواست بیش از اندازه بزرگ است.", 413)
        response = await call_next(request)
    except PortalError as error:
        response = JSONResponse({"detail": error.message}, status_code=error.status)
    response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                             "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
                             "Content-Security-Policy": CSP})
    return response


async def portal_error(request, error):
    return JSONResponse({"detail": error.message}, status_code=error.status)


async def invalid_input(request, error):
    return JSONResponse({"detail": "ورودی معتبر نیست؛ مقدارها و محدودیت طول را بررسی کنید."}, status_code=400)


async def unexpected_error(request, error):
    return JSONResponse({"detail": "عملیات کامل نشد؛ کمی بعد دوباره تلاش کنید."}, status_code=503)


def index():
    return FileResponse(PUBLIC / "index.html")


def health():
    return {"status": "ok"}
