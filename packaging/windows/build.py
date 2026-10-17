"""ورودی ساخت فقط نشانی عمومی سرور است؛ رازها به فرایند ساخت منتقل نمی‌شوند."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rasam import __version__


def service_url(value, local):
    parts = urlsplit(value)
    allowed = parts.scheme == "https" or (local and parts.scheme == "http" and parts.hostname == "127.0.0.1")
    if (not allowed or not parts.hostname or parts.username or parts.password or parts.query
            or parts.fragment or any(char.isspace() for char in value)):
        raise ValueError("نشانی سرور باید عمومی و بدون کلید یا رمز باشد؛ loopback فقط با --local-test مجاز است.")
    return value.rstrip("/")


def clean_environment():
    # PATH برای ابزارهای ساخت لازم است؛ هیچ تنظیم مشتری یا سرویس مدل به آن‌ها نمی‌رود.
    return {key: value for key, value in os.environ.items()
            if not key.startswith("RASAM_") and key not in {"UPSTREAM_API_KEY", "OPENAI_API_KEY"}}


def make_bundle(url, output):
    staging = output / "service"
    staging.mkdir(parents=True, exist_ok=True)
    service = staging / "desktop-service.json"
    service.write_text(json.dumps({"gateway_url": url}), encoding="utf-8")
    env = {**clean_environment(), "RASAM_BUILD_SERVICE_FILE": str(service)}
    subprocess.run([sys.executable, "-m", "PyInstaller", str(ROOT / "packaging/windows/rasam.spec"),
                    "--distpath", str(output / "dist"), "--workpath", str(output / "work"),
                    "--noconfirm"], cwd=ROOT, env=env, check=True)
    return output / "dist/Rasam"


def verify_bundle(bundle):
    required = [bundle / "Rasam.exe", bundle / "_internal/desktop-service.json",
                bundle / "_internal/rasam/desktop/static/index.html",
                bundle / "_internal/templates/customer/profile.yaml"]
    if not all(path.is_file() for path in required):
        raise ValueError("بستهٔ برنامه ناقص است.")
    forbidden = {".env", ".dev.vars", "auth.json", "chroma.sqlite3"}
    for path in bundle.rglob("*"):
        if path.is_file() and (path.name in forbidden or "customers" in path.relative_to(bundle).parts):
            raise ValueError("دادهٔ مشتری یا فایل راز در بسته پیدا شد؛ ساخت متوقف شد.")
    return sum(path.stat().st_size for path in bundle.rglob("*") if path.is_file())


def verify_no_secrets(bundle, values):
    secrets = [value.encode() for value in values if value and len(value) >= 8]
    if not secrets:
        return
    overlap = max(map(len, secrets))
    for path in bundle.rglob("*"):
        if not path.is_file():
            continue
        tail = b""
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                content = tail + chunk
                if any(secret in content for secret in secrets):
                    raise ValueError("راز پیکربندی در بسته پیدا شد؛ خروجی نباید تحویل داده شود.")
                tail = content[-overlap:]


def configured_secrets():
    values = {**dotenv_values(ROOT / ".env"), **dotenv_values(ROOT / "gateway/.dev.vars"), **os.environ}
    return [value for key, value in values.items() if "API_KEY" in key or "PASSWORD" in key]


def make_installer(compiler, bundle, output):
    subprocess.run([str(compiler), "/Qp", f"/DBundleDir={bundle}", f"/DAppVersion={__version__}",
                    f"/DOutputDir={output}", str(ROOT / "packaging/windows/rasam.iss")], check=True)
    installer = output / "RasamSetup.exe"
    digest = hashlib.file_digest(installer.open("rb"), "sha256").hexdigest()
    installer.with_suffix(".exe.sha256").write_text(digest + "  " + installer.name + "\n", encoding="ascii")
    return installer


def main(argv=None):
    parser = argparse.ArgumentParser(description="ساخت نسخهٔ رومیزی ویندوز")
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--local-test", action="store_true")
    parser.add_argument("--iscc", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "exports/windows-build")
    args = parser.parse_args(argv)
    try:
        if sys.platform != "win32":
            raise ValueError("ساخت این بسته باید روی ویندوز انجام شود.")
        url = service_url(args.gateway_url, args.local_test)
        output = args.output.resolve()
        bundle = make_bundle(url, output)
        size = verify_bundle(bundle)
        verify_no_secrets(bundle, configured_secrets())
        installer = make_installer(args.iscc, bundle, output) if args.iscc else None
        print(f"بسته آماده است؛ اندازه: {size / 1024**2:.1f} MiB")
        print(installer or bundle)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ساخت کامل نشد ({type(error).__name__})؛ خروجی ابزار ساخت را بررسی کنید.")
        return 1


if __name__ == "__main__":
    from rasam.console import use_utf8
    use_utf8()
    raise SystemExit(main())
