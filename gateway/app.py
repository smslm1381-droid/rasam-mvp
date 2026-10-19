"""API سازگار با مدل؛ متن درخواست و نتیجه ذخیره یا لاگ نمی‌شود."""

import json
import math
import logging
import re
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from gateway import licenses, upstream

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def error(code, message, status):
    return JSONResponse({"error": {"code": code, "message": message, "type": "gateway_error"}},
                        status_code=status, headers={"Cache-Control": "no-store"})


def license_error(code):
    status, message = licenses.ERRORS[code]
    return error(code, message, status)


def key_from(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    key = header[7:]
    return key if 20 <= len(key) <= 200 and key.isascii() else None


async def bounded_body(request):
    chunks = []
    length = 0
    async for chunk in request.stream():
        length += len(chunk)
        if length > 512000:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def payload(body, env):
    if not isinstance(body, dict) or body.get("stream"):
        raise ValueError("invalid request")
    messages = body.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 20:
        raise ValueError("invalid messages")
    clean = []
    for message in messages:
        if (not isinstance(message, dict) or message.get("role") not in ("system", "user", "assistant")
                or not isinstance(message.get("content"), str)):
            raise ValueError("invalid message")
        clean.append({"role": message["role"], "content": message["content"]})
    maximum = int(getattr(env, "UPSTREAM_MAX_TOKENS", "2048"))
    requested = body.get("max_completion_tokens", body.get("max_tokens", maximum))
    if type(requested) is not int or not 1 <= requested <= 100000:
        raise ValueError("invalid token limit")
    result = {"model": env.UPSTREAM_MODEL, "messages": clean, "max_tokens": min(requested, maximum)}
    temperature = body.get("temperature", 0.1)
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("invalid temperature")
    result["temperature"] = temperature
    if body.get("reasoning_effort") in ("none", "minimal", "low", "medium", "high"):
        result["reasoning_effort"] = body["reasoning_effort"]
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version(request: Request):
    env = request.scope["env"]
    latest = getattr(env, "LATEST_VERSION", "")
    download = getattr(env, "DOWNLOAD_URL", "")
    try:
        parts = urlsplit(download)
    except ValueError:
        parts = urlsplit("")
    valid_url = (parts.scheme == "https" and parts.hostname and not parts.username
                 and not parts.password and not any(char.isspace() for char in download))
    valid_version = bool(re.fullmatch(r"\d{1,5}\.\d{1,5}\.\d{1,5}", latest))
    return JSONResponse({"version": latest if valid_version else None,
                         "download_url": download if valid_url else None}, headers={"Cache-Control": "no-store"})


@app.get("/license/status")
async def license_status(request: Request):
    key = key_from(request)
    if key is None:
        return license_error("license_invalid")
    try:
        env = request.scope["env"]
        status = await licenses.Licenses(env.DB).status(key)
        if status is None:
            return license_error("license_invalid")
        status["model"] = status.get("model") or env.UPSTREAM_MODEL
        status["support_url"] = getattr(env, "SUPPORT_URL", "")
        return JSONResponse(status, headers={"Cache-Control": "no-store"})
    except Exception:
        return error("gateway_unavailable", "سرور رصام اکنون در دسترس نیست؛ کمی بعد دوباره تلاش کنید.", 503)


@app.post("/v1/chat/completions")
async def completion(request: Request):
    key = key_from(request)
    if key is None:
        return license_error("license_invalid")
    try:
        raw = await bounded_body(request)
        if raw is None:
            return error("request_too_large", "متن درخواست بیش از اندازه بزرگ است.", 413)
        env = request.scope["env"]
        prepared = payload(json.loads(raw), env)
    except (ValueError, TypeError, UnicodeError):
        return error("invalid_request", "درخواست مدل معتبر نیست؛ فقط پیام متنی و پاسخ بدون جریان پشتیبانی می‌شود.", 400)
    except Exception:
        return error("gateway_unavailable", "پیکربندی سرور رصام آماده نیست؛ با پشتیبانی تماس بگیرید.", 503)
    try:
        row, reason = await licenses.Licenses(env.DB).reserve(key)
        if reason:
            return license_error(reason)
        prepared["model"] = row.get("model") or env.UPSTREAM_MODEL
        result = await upstream.chat(env, prepared)
        if result is None:
            return error("upstream_unavailable", "سرویس مدل اکنون پاسخ نمی‌دهد؛ کمی بعد دوباره تلاش کنید.", 503)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
    except Exception as diagnostic_error:
        logging.error("gateway failure type: %s", type(diagnostic_error).__name__)
        return error("gateway_unavailable", "سرور رصام اکنون در دسترس نیست؛ کمی بعد دوباره تلاش کنید.", 503)
