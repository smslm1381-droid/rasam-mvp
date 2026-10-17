"""اجرای دستور مدیریتی D1 با ابزار رسمی؛ کلید خام لایسنس وارد فرمان نمی‌شود."""

import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def execute(sql, remote=False):
    folder = ROOT / ".wrangler"
    folder.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".sql", dir=folder, delete=False) as file:
        file.write(sql)
        path = Path(file.name)
    try:
        result = subprocess.run(["uv", "run", "pywrangler", "d1", "execute", "DB",
                                 "--remote" if remote else "--local", "--file", str(path), "--json"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
                                env={**os.environ, "PYWRANGLER_LOG": "error", "WRANGLER_SEND_METRICS": "false"})
        if result.returncode != 0:
            raise RuntimeError("اجرای D1 ناموفق بود؛ نصب Node و uv، ورود Cloudflare و تنظیمات پایگاه را بررسی کنید.")
        data = json.loads(result.stdout)
        return [row for item in data for row in item.get("results", [])]
    finally:
        path.unlink(missing_ok=True)
