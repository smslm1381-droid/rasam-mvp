"""HTTP محلی: احراز دسترسی و نمایش Answer، بدون تولید یا اجرای کوئری."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

from rasam import config
from rasam.core import exporting
from rasam.desktop.security import LocalSecurity
from rasam.desktop.session import Session
from rasam.desktop.connecting import routes
from rasam.desktop.profiles import routes as profile_routes
from rasam.desktop.teaching import routes as teaching_routes
from rasam.desktop.licensing import routes as licensing_routes
from rasam.core.licensing import LicenseManager

STATIC_DIR = Path(__file__).resolve().parent / "static"


class Question(BaseModel):
    question: str = Field(max_length=10000)


def create_app(token: str | None = None, answerer=None, license_manager=None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = token or secrets.token_urlsafe(32)
    app.state.session = Session(answerer)
    app.state.licensing = license_manager or LicenseManager()
    app.state.shutdown = None
    app.state.licensing.configure_runtime()
    setup_routes, app.state.setup = routes()
    app.include_router(setup_routes)
    app.include_router(profile_routes(app))
    app.include_router(teaching_routes(app))
    app.include_router(licensing_routes(app))
    app.add_middleware(LocalSecurity, token=app.state.token)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.add_api_route("/", index, methods=["GET"])
    app.add_api_route("/status", status, methods=["GET"])
    app.add_api_route("/shutdown", shutdown_route(app), methods=["POST"])
    app.add_api_route("/ask", ask_route(app), methods=["POST"])
    app.add_api_route("/export/{answer_id}/{kind}", export_route(app), methods=["GET"])
    app.add_exception_handler(RequestValidationError, invalid_request)
    return app


async def invalid_request(request, error):
    return JSONResponse({"detail": "ورودی درخواست معتبر نیست؛ مقدارها را بررسی کنید."}, status_code=422)


def index():
    return FileResponse(STATIC_DIR / "index.html")


def status():
    settings = config.settings
    return {"configured": settings is not None,
            "customer": settings.customer.name if settings else None,
            "capabilities": sorted(settings.customer.capabilities) if settings else []}


def shutdown_route(app):
    def shutdown():
        if app.state.shutdown is None:
            return JSONResponse({"ok": False, "message": "بستن برنامه در این اجرا ممکن نیست."}, status_code=503)
        return JSONResponse({"ok": True}, background=BackgroundTask(app.state.shutdown))
    return shutdown


def ask_route(app):
    def ask(body: Question, response: Response):
        app.state.licensing.configure_runtime()
        result, answer_id = app.state.session.ask(body.question)
        response.headers["X-Answer-ID"] = answer_id
        return asdict(result)
    return ask


def export_route(app):
    def export(answer_id: str, kind: Literal["csv", "excel"]):
        result = app.state.session.result(answer_id)
        if result is None or result.error or result.message:
            raise HTTPException(404, "این نتیجه دیگر در دسترس نیست؛ دوباره سوال را بپرسید.")
        if config.settings is None or not exporting.is_enabled(kind):
            raise HTTPException(403, "این نوع خروجی برای شما فعال نیست.")
        content = exporting.CSV_BOM + exporting.to_csv(result.rows) if kind == "csv" else exporting.to_excel(result.rows)
        media = "text/csv" if kind == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        suffix = "csv" if kind == "csv" else "xlsx"
        return Response(content, media_type=media,
                        headers={"Content-Disposition": f'attachment; filename="result.{suffix}"'})
    return export
