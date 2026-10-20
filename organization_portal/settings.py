"""محیط محلی و میزبانی از هم مشخص‌اند؛ رازها از متغیر میزبان می‌آیند، نه فایل مشتری."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet

from organization_portal.errors import PortalError


@dataclass
class Settings:
    home: Path
    origin: str
    key: str = field(repr=False)
    local: bool = False
    backend_key: str = field(default="", repr=False)
    storage_url: str = ""
    storage_key: str = field(default="", repr=False)
    quota_policy: str = "complete_answer"

    def validate(self):
        try:
            Fernet(self.key.encode())
            self.origin = self.origin.rstrip("/")
            parts = urlsplit(self.origin)
            local_host = parts.hostname in {"127.0.0.1", "localhost", "::1"}
            if not parts.hostname or parts.path or parts.query or parts.fragment or parts.username or parts.password:
                raise ValueError()
            if parts.scheme != "https" and not (self.local and parts.scheme == "http" and local_host):
                raise ValueError()
            if not self.local and (len(self.backend_key) < 40 or len(self.storage_key) < 40 or not self.storage_url):
                raise ValueError()
            if self.storage_url and (urlsplit(self.storage_url).scheme != "https" or not urlsplit(self.storage_url).hostname):
                raise ValueError()
            if self.quota_policy != "complete_answer":
                raise ValueError()
        except (ValueError, TypeError):
            raise PortalError("تنظیمات سرور سازمانی کامل یا معتبر نیست؛ راهنمای استقرار را بررسی کنید.", 503) from None
        return self

    @property
    def cookie(self):
        return "rasam_org" if self.local else "__Host-rasam_org"


def from_environment():
    home = os.getenv("RASAM_ORG_HOME", "").strip()
    if not home:
        raise PortalError("مسیر RASAM_ORG_HOME را برای دادهٔ موقت سرور تعیین کنید.", 503)
    key = os.getenv("RASAM_ORG_MASTER_KEY", "")
    if not key and os.getenv("RASAM_ORG_LOCAL") == "1":
        from organization_portal.local_key import read
        key = read(Path(home))
    return Settings(Path(home), os.getenv("RASAM_ORG_ORIGIN", ""), key,
        local=os.getenv("RASAM_ORG_LOCAL") == "1", backend_key=os.getenv("RASAM_ORG_BACKEND_KEY", ""),
        storage_url=os.getenv("RASAM_ORG_STORAGE_URL", ""), storage_key=os.getenv("RASAM_ORG_STORAGE_KEY", ""),
        quota_policy=os.getenv("RASAM_ORG_QUOTA_POLICY", "complete_answer")).validate()
