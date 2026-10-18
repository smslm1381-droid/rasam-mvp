"""نمایش و فعال‌سازی لایسنس رومیزی؛ اجرای سهمیه فقط در سرور واسط است."""

from dataclasses import replace
import re
import sys
import threading
from urllib.parse import urlsplit
import httpx

from rasam import config, vault, desktop_service
from rasam.core.licensing_messages import MESSAGES

KEY = re.compile(r"^[A-Za-z0-9_-]{20,200}$")


def failed(code, message):
    return {"valid": False, "code": code, "message": message}


def license_failure(code):
    return failed(code, MESSAGES.get(code, "بررسی لایسنس ممکن نشد؛ کمی بعد دوباره تلاش کنید."))


def clean_status(data):
    if not isinstance(data, dict) or type(data.get("valid")) is not bool:
        raise ValueError("invalid status")
    if not isinstance(data.get("customer"), str) or len(data["customer"]) > 200:
        raise ValueError("invalid customer")
    if not isinstance(data.get("model"), str) or not 1 <= len(data["model"]) <= 200:
        raise ValueError("invalid model")
    for name in ("expires_at", "days_remaining", "daily_limit", "used_today"):
        if type(data.get(name)) is not int or data[name] < 0:
            raise ValueError("invalid number")
    if data.get("plan") not in ("monthly", "yearly"):
        raise ValueError("invalid plan")
    code = data.get("code")
    if (data["valid"] and code is not None) or (not data["valid"] and code not in MESSAGES):
        raise ValueError("invalid validity")
    result = {name: data[name] for name in ("valid", "customer", "model", "expires_at",
              "days_remaining", "daily_limit", "used_today", "plan")}
    support = data.get("support_url", "")
    parts = urlsplit(support) if isinstance(support, str) else None
    result["support_url"] = support if parts and parts.scheme == "https" and parts.hostname and not (parts.username or parts.password) else ""
    return {**result, "code": code, "message": "" if data["valid"] else MESSAGES[code]}


def fetch_status(url, key):
    if not url:
        return failed("configuration", "نشانی سرور رصام در این نسخه تنظیم نشده است؛ با پشتیبانی تماس بگیرید.")
    if not KEY.fullmatch(key):
        return license_failure("license_invalid")
    try:
        response = httpx.get(url + "/license/status", headers={"Authorization": "Bearer " + key},
                             timeout=10, follow_redirects=False)
        if len(response.content) > 20000:
            raise ValueError("large status")
        data = response.json()
        if response.status_code != 200:
            detail = data.get("error", {}) if isinstance(data, dict) else {}
            return license_failure(detail.get("code")) if isinstance(detail, dict) else license_failure(None)
        return clean_status(data)
    except (httpx.HTTPError, OSError):
        return failed("network", "ارتباط با سرور رصام برقرار نشد؛ اینترنت را بررسی کنید و دوباره تلاش کنید.")
    except Exception:
        return failed("response", "پاسخ بررسی لایسنس قابل خواندن نبود؛ دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.")


class LicenseManager:
    def __init__(self, secret_name="LICENSE_KEY"):
        self.enabled = config.DESKTOP_MODE
        self.secret_name = secret_name
        self._key = ""
        self.info = failed("missing", "برای شروع، کد لایسنس خود را وارد کنید.")
        self.lock = threading.RLock()

    def public_status(self):
        if not self.enabled:
            return {"required": False, "valid": True}
        return {"required": True, **{key: value for key, value in self.info.items() if key != "model"}}

    def refresh(self):
        with self.lock:
            if not self.enabled:
                return self.public_status()
            # اجازهٔ یک‌بارهٔ Keychain را برای همان لایسنس در هر درخواست تکرار نمی‌کنیم.
            secret = vault.Result(True, value=self._key) if self._key else vault.read_secret(self.secret_name)
            if not secret.ok:
                self.info = failed("vault", secret.error)
            elif secret.value:
                self._key = secret.value
                self.info = fetch_status(desktop_service.gateway_url(), secret.value)
            else:
                self.info = failed("missing", "برای شروع، کد لایسنس خود را وارد کنید.")
            self.configure_runtime()
            return self.public_status()

    def activate(self, key):
        with self.lock:
            if not self.enabled:
                return {"ok": False, "message": "فعال‌سازی لایسنس مخصوص حالت رومیزی است."}
            key = key.strip()
            info = fetch_status(desktop_service.gateway_url(), key)
            if not info["valid"]:
                return {"ok": False, **{name: value for name, value in info.items() if name != "model"}}
            saved = vault.write_secret(self.secret_name, key)
            if not saved.ok:
                return {"ok": False, "message": saved.error}
            self._key = key
            self.info = info
            self.configure_runtime()
            return {"ok": True, **self.public_status()}

    def configure_runtime(self):
        if not self.enabled or config.settings is None:
            return
        key = self._key
        url = desktop_service.gateway_url()
        base_url = url + "/v1" if url else ""
        model = self.info.get("model", "")
        current = config.settings
        if (current.llm_api_key, current.llm_base_url, current.llm_model) == (key, base_url, model):
            return
        # حتی اگر کاربر متغیر توسعه صادر کرده باشد، مسیر رومیزی فقط واسط را می‌بیند.
        config.settings = replace(current, llm_api_key=key, llm_base_url=base_url, llm_model=model)
        llm = sys.modules.get("rasam.core.llm")
        if llm is not None:
            llm._client.cache_clear()
