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
from pydantic import BaseModel, Field

from rasam import config
from rasam.core import exporting
from rasam.desktop.security import LocalSecurity
from rasam.desktop.session import Session

STATIC_DIR = Path(__file__).resolve().parent / "static"


class Question(BaseModel):
    question: str = Field(max_length=10000)


def create_app(token: str | None = None, answerer=None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = token or secrets.token_urlsafe(32)
    app.state.session = Session(answerer)
    app.add_middleware(LocalSecurity, token=app.state.token)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.add_api_route("/", index, methods=["GET"])
    app.add_api_route("/status", status, methods=["GET"])
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


def ask_route(app):
    def ask(body: Question, response: Response):
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
