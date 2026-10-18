"""سنجه از همان HTTP کاربر می‌گذرد؛ رمز در آرگومان خط فرمان قرار نمی‌گیرد."""

from urllib.parse import urlsplit
import httpx

from rasam.core.answer import Answer
from rasam.desktop.instance import DesktopInstance


def http_answerer(url, headers):
    parts = urlsplit(url)
    local = parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost", "::1"}
    if (not parts.hostname or (parts.scheme != "https" and not local)
            or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError("نشانی سنجه باید HTTPS یا loopback و بدون رمز باشد.")

    def answer(question):
        try:
            response = httpx.post(url.rstrip("/") + "/ask", headers=headers,
                                  json={"question": question}, timeout=180, follow_redirects=False)
            if response.status_code != 200:
                return Answer(question=question, error=f"سرور سنجه پاسخ HTTP {response.status_code} داد.")
            result = Answer(**response.json())
            if result.question != question or not isinstance(result.rows, list):
                raise ValueError("invalid answer")
            if (not all(isinstance(row, dict) for row in result.rows)
                    or any(value is not None and not isinstance(value, str)
                           for value in (result.error, result.message))):
                raise ValueError("invalid answer fields")
            return result
        except Exception:
            return Answer(question=question, error="دریافت پاسخ سنجه از سرور انجام نشد.")
    return answer


def desktop_answerer(home):
    url = DesktopInstance(home).read_url()
    if not url:
        raise ValueError("نشست رومیزی آماده نیست؛ ابتدا برنامه را باز کنید.")
    base, _, token = url.partition("/?token=")
    headers = {"X-Rasam-Token": token}
    # در اجرای بدون مرورگر، رویداد بارگذاری صفحه اعتبار ذخیره‌شده را تازه نمی‌کند.
    try:
        response = httpx.get(base + "/license/status", headers=headers, timeout=20, follow_redirects=False)
        if response.status_code != 200 or response.json().get("valid") is not True:
            raise ValueError("لایسنس برنامه آماده نیست؛ وضعیت اعتبار را در رصام بررسی کنید.")
    except (httpx.HTTPError, TypeError, AttributeError) as error:
        raise ValueError("ارتباط با نسخهٔ رومیزی برای بررسی اعتبار برقرار نشد.") from error
    return http_answerer(base, headers)
