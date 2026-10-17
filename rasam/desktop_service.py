"""نشانی عمومی سرویس از پیکربندی می‌آید؛ نصب‌کننده هیچ کلید مدلی ندارد."""

import json
from urllib.parse import urlsplit
from rasam import config


def gateway_url():
    try:
        raw = config.env_value("GATEWAY_URL")
        if not raw:
            path = config.PROJECT_ROOT / "desktop-service.json"
            raw = json.loads(path.read_text(encoding="utf-8-sig")).get("gateway_url")
        if not isinstance(raw, str):
            return None
        parts = urlsplit(raw)
        local = parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost")
        if (parts.scheme != "https" and not local) or not parts.hostname:
            return None
        if parts.username or parts.password or parts.query or parts.fragment:
            return None
        return raw.rstrip("/")
    except (OSError, ValueError, TypeError, AttributeError):
        return None
