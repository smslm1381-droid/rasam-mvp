"""کلید اجرای محلی در انبار رمز سیستم‌عامل است؛ میزبان ابری از secret محیط استفاده می‌کند."""

import hashlib

from cryptography.fernet import Fernet

from organization_portal.errors import PortalError


def read(home, create=False):
    from rasam import vault
    name = "ORG_SERVER_KEY_" + hashlib.sha256(str(home.resolve()).encode()).hexdigest()[:20].upper()
    result = vault.read_secret(name)
    if not result.ok:
        raise PortalError("انبار امن رمز سیستم برای کلید سرور محلی در دسترس نیست.", 503)
    if result.value:
        return result.value
    if not create:
        raise PortalError("ابتدا فرمان init محیط سازمانی را اجرا کنید.", 503)
    key = Fernet.generate_key().decode()
    if not vault.write_secret(name, key).ok:
        raise PortalError("ذخیرهٔ کلید محلی انجام نشد.", 503)
    return key
