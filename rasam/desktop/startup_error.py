"""رد خطا بدون متن استثنا نگه داشته می‌شود تا توکن و راز وارد گزارش نشود."""

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import traceback

from rasam import __version__


def record_error(home: Path, error: Exception) -> Path | None:
    frames = traceback.extract_tb(error.__traceback__)
    report = {
        "version": __version__,
        "time": datetime.now(timezone.utc).isoformat(),
        "platform": sys.platform,
        "frozen": bool(getattr(sys, "frozen", False)),
        "error": type(error).__name__,
        "frames": [{"file": Path(frame.filename).name, "line": frame.lineno,
                    "function": frame.name} for frame in frames[-20:]],
    }
    for name in ("errno", "winerror"):
        value = getattr(error, name, None)
        if type(value) is int:
            report[name] = value
    try:
        home.mkdir(parents=True, exist_ok=True)
        path = home / "startup-error.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    except OSError:
        return None
