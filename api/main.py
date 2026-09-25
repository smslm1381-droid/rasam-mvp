"""API رصام؛ فقط احراز هویت و سریالایزکردن Answer."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

import config
from graph import answer

app = FastAPI(title="Rasam API", version="1.0")


class AskRequest(BaseModel):
    question: str


def _check_api_key(api_key: str | None) -> None:
    """دسترسی را پیش از رسیدن درخواست به گراف بررسی می‌کند."""
    configured = config.settings.api_key
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="کلید API در تنظیمات سرور تعریف نشده است.",
        )
    if not api_key or not secrets.compare_digest(api_key, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="کلید API معتبر نیست.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask")
def ask(
    request: AskRequest,
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict:
    _check_api_key(x_api_key)
    return asdict(answer(request.question))