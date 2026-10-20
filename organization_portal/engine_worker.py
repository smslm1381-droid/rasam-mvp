"""ورودی داخلی هسته؛ فقط JSON کنترل‌شده می‌خواند و هیچ کد مدل را اجرا نمی‌کند."""

from dataclasses import asdict
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml


def prepare(home, job):
    os.environ.update(RASAM_DESKTOP="1", RASAM_HOME=str(home), RASAM_CUSTOMER="organization",
                      RASAM_ORGANIZATION_URI=job["uri"], RASAM_LLM_API_KEY="not-configured")
    for name in ("API_KEY", "BASE_URL", "MODEL"):
        os.environ["RASAM_LLM_" + name] = os.getenv("RASAM_ORG_LLM_" + name, "") or (
            "not-configured" if name == "API_KEY" else "")
    from organization_portal.network import check_destination, secure_uri
    uri = secure_uri(job["db_type"], job["uri"])
    check_destination(uri, job["allowed_hosts"], job.get("local", False))
    if job.get("ca_pem"):
        ca = home / "ca.pem"
        ca.write_text(job["ca_pem"], encoding="utf-8")
        parts = urlsplit(uri)
        query = parse_qsl(parts.query) + [("tlsCAFile", str(ca))]
        uri = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    os.environ["RASAM_ORGANIZATION_URI"] = uri
    profile = home / "customers/organization"
    profile.mkdir(parents=True)
    values = {"db_type": job["db_type"], "connection_env": "ORGANIZATION_URI", "database": job["database"],
              "allowed_sources": job.get("sources", []), "capabilities": ["repair", "summary", "chart"],
              "limits": {"max_rows": 1000, "max_attempts": 2}}
    (profile / "profile.yaml").write_text(yaml.safe_dump(values), encoding="utf-8")
    (profile / "documentation.md").write_text(job.get("documentation", ""), encoding="utf-8")
    return uri


def execute(home, job):
    if job["mode"] == "export":
        return export(job)
    uri = prepare(home, job)
    from rasam import config
    from rasam.databases import registry
    agent = registry.AGENTS[job["db_type"]](connection_uri=uri, database=job["database"],
                                         allowed_sources=frozenset(job.get("sources", [])))
    access = agent.check_read_only()
    if not access.read_only:
        return {"ok": False, "category": "read_only", "message": "اتصال اجازهٔ نوشتن دارد؛ حساب فقط‌خواندنی لازم است."}
    if job["mode"] == "probe":
        return {"ok": True, "sources": agent.list_sources(), "message": "اتصال امن و فقط‌خواندنی برقرار شد."}
    if not all(os.getenv("RASAM_ORG_LLM_" + name) for name in ("API_KEY", "BASE_URL", "MODEL")):
        return {"ok": False, "message": "سرویس مدل سرور هنوز تنظیم نشده است؛ هیچ درخواست مدلی ارسال نشد."}
    config.settings = config._load(require_model=False)
    from rasam.core.graph import answer
    result = answer(job["question"], history=job.get("history", []))
    return outcome(result)


def export(job):
    os.environ["RASAM_DESKTOP"] = "1"
    from rasam.core import exporting
    if job["kind"] == "csv":
        content = (exporting.CSV_BOM + exporting.to_csv(job["rows"])).encode("utf-8")
    elif job["kind"] == "excel":
        content = exporting.to_excel(job["rows"])
    else:
        raise ValueError()
    return {"ok": True, "content": base64.b64encode(content).decode()}


def outcome(result):
    from rasam.core import charting
    data = result.source is not None and result.query is not None
    valid = not result.error and (data or bool(result.message))
    chart_needed = data and charting.wants_chart(result.question)
    complete = valid and (not data or result.summary is not None) and (not chart_needed or result.chart is not None)
    return {"ok": True, "answer": asdict(result), "valid": valid, "complete": complete}


def main():
    try:
        raw = sys.stdin.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError()
        job = json.loads(raw)
        with tempfile.TemporaryDirectory(prefix="rasam-org-job-") as directory:
            result = execute(Path(directory), job)
    except Exception:
        result = {"ok": False, "message": "اتصال یا اجرای درخواست کامل نشد؛ تنظیمات شبکه، گواهی و حساب فقط‌خواندنی را بررسی کنید."}
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
