"""فقط انتخاب مشتری فعال روی دیسک است؛ هیچ راز یا رشتهٔ اتصال اینجا نیست."""

import json
from pathlib import Path


def read_customer(home: Path):
    try:
        data = json.loads((home / "desktop.json").read_text(encoding="utf-8-sig"))
        value = data.get("customer")
        return value if isinstance(value, str) else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def write_customer(home: Path, name: str):
    home.mkdir(parents=True, exist_ok=True)
    temporary = home / "desktop.json.tmp"
    temporary.write_text(json.dumps({"customer": name}), encoding="utf-8")
    temporary.replace(home / "desktop.json")
