"""API رصام؛ فقط احراز هویت و سریالایزکردن Answer."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from rasam import config
from rasam.core import exporting
from rasam.core.graph import answer

app = FastAPI(title="Rasam API", version="1.0")


class AskRequest(BaseModel):
    question: str
    export: Literal["csv", "excel"] | None = None


def _check_api_key(api_key: str | None) -> None:
    """دسترسی را پیش از رسیدن درخواست به گراف بررسی می‌کند."""
    configured = config.settings.api_key
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="کلید API در تنظیمات سرور تعریف نشده است.",
        )
    # هر دو به بایت تبدیل می‌شوند: `compare_digest` روی رشته‌ی غیر-ASCII
    # استثنا پرتاب می‌کند، و کلیدی که کاربر با حروف فارسی بسازد باید ۴۰۱
    # بگیرد نه ۵۰۰.
    if not api_key or not secrets.compare_digest(api_key.encode(), configured.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="کلید API معتبر نیست.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


_MEDIA = {
    "csv": "text/csv",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_FILENAME = {"csv": "result.csv", "excel": "result.xlsx"}


def _file(kind: str, rows: list[dict]) -> Response:
    content = exporting.to_csv(rows) if kind == "csv" else exporting.to_excel(rows)
    return Response(
        content=content,
        media_type=_MEDIA[kind],
        headers={"Content-Disposition": f'attachment; filename="{_FILENAME[kind]}"'},
    )


@app.post("/ask")
def ask(
    request: AskRequest,
    x_api_key: Annotated[str | None, Header()] = None,
):
    _check_api_key(x_api_key)
    result = answer(request.question)

    # خروجی فایل فقط وقتی معنا دارد که جدولی وجود داشته باشد. قبلاً سوالِ
    # ردشده یا جوابِ «این داده موجود نیست» هم یک CSV **خالی** با کد ۲۰۰
    # می‌گرفت، یعنی خطا بی‌صدا به یک فایل تهی تبدیل می‌شد.
    if request.export and not result.error and not result.message:
        if not exporting.is_enabled(request.export):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"خروجی {request.export} برای این مشتری فعال نیست.",
            )
        return _file(request.export, result.rows)
    return asdict(result)
