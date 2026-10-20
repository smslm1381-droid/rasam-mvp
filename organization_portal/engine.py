"""تنظیمات و حافظهٔ هسته برای هر درخواست در فرایند تازه‌اند؛ بین سازمان‌ها مشترک نمی‌شوند."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading

from organization_portal.errors import PortalError

ROOT = Path(__file__).resolve().parent.parent


class Engine:
    def __init__(self, local=False):
        self.local = local
        self.capacity = threading.BoundedSemaphore(1)

    def run(self, job):
        if not self.capacity.acquire(timeout=5):
            raise PortalError("سرور آزمایشی مشغول است؛ کمی بعد دوباره تلاش کنید.", 503)
        try:
            env = {key: value for key, value in os.environ.items() if not key.startswith("RASAM_")
                   or key.startswith("RASAM_ORG_LLM_")}
            env["RASAM_DESKTOP"] = "1"
            value = {**job, "local": self.local}
            result = subprocess.run([sys.executable, "-m", "organization_portal.engine_worker"],
                input=json.dumps(value, ensure_ascii=False), capture_output=True, text=True,
                encoding="utf-8", env=env, cwd=ROOT, timeout=150, check=False)
            response = json.loads(result.stdout.strip().splitlines()[-1])
            if result.returncode or not isinstance(response, dict):
                raise ValueError()
            return response
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            raise PortalError("اجرای هسته کامل نشد؛ اتصال و وضعیت سرور را بررسی کنید.", 503) from None
        finally:
            self.capacity.release()
