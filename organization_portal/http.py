"""نشست، مبدأ و CSRF در سرور بررسی می‌شوند؛ شناسهٔ سازمان ورودی قابل اعتماد نیست."""

import hmac

from organization_portal import passwords
from organization_portal.errors import PortalError


def current(request, required=True):
    settings = request.app.state.settings
    token = request.cookies.get(settings.cookie, "")
    user = request.app.state.accounts.current(token)
    if not user and required:
        raise PortalError("ابتدا وارد حساب سازمانی شوید.", 401)
    if request.method not in {"GET", "HEAD"} and user:
        expected = passwords.digest("csrf:" + token)
        supplied = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise PortalError("اعتبار فرم تمام شده؛ صفحه را تازه کنید.", 403)
    return user


def token(request):
    return request.cookies.get(request.app.state.settings.cookie, "")


def csrf(request):
    return passwords.digest("csrf:" + token(request))


def protect(request):
    settings = request.app.state.settings
    if not settings.local:
        supplied = request.headers.get("X-Rasam-Proxy-Key", "")
        if not hmac.compare_digest(supplied.encode(), settings.backend_key.encode()):
            raise PortalError("دسترسی مستقیم به سرور مجاز نیست.", 403)
    if request.method not in {"GET", "HEAD"} and request.headers.get("Origin") != settings.origin:
        raise PortalError("مبدأ درخواست معتبر نیست.", 403)
    if len(request.headers.get("Cookie", "")) > 16000:
        raise PortalError("درخواست بیش از اندازه بزرگ است.", 413)
