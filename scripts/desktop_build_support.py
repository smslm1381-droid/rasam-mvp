"""قواعد مشترک ساخت رومیزی؛ کنترل نشانی و جلوگیری از بسته‌بندی رازها."""

import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def service_url(value, local):
    parts = urlsplit(value)
    allowed = parts.scheme == "https" or (local and parts.scheme == "http" and parts.hostname == "127.0.0.1")
    if (not allowed or not parts.hostname or parts.username or parts.password or parts.query
            or parts.fragment or any(char.isspace() for char in value)):
        raise ValueError("نشانی سرور باید عمومی و بدون کلید یا رمز باشد؛ loopback فقط با --local-test مجاز است.")
    return value.rstrip("/")


def clean_environment():
    # PATH برای ابزارهای ساخت لازم است؛ هیچ تنظیم مشتری یا سرویس مدل به آن‌ها نمی‌رود.
    return {key: value for key, value in os.environ.items()
            if not key.startswith("RASAM_") and key not in {"UPSTREAM_API_KEY", "OPENAI_API_KEY"}}


def verify_no_secrets(bundle, values):
    secrets = [value.encode() for value in values if value and len(value) >= 8]
    if not secrets:
        return
    overlap = max(map(len, secrets))
    for path in bundle.rglob("*"):
        if not path.is_file():
            continue
        tail = b""
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                content = tail + chunk
                if any(secret in content for secret in secrets):
                    raise ValueError("راز پیکربندی در بسته پیدا شد؛ خروجی نباید تحویل داده شود.")
                tail = content[-overlap:]


def configured_secrets():
    values = {**dotenv_values(ROOT / ".env"), **dotenv_values(ROOT / "gateway/.dev.vars"), **os.environ}
    return [value for key, value in values.items() if "API_KEY" in key or "PASSWORD" in key]
