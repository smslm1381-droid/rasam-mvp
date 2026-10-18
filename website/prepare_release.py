"""فقط فرادادهٔ عمومی و هش نسخه را می‌سازد؛ فایل نصب جداگانه در R2 بارگذاری می‌شود."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rasam import __version__

# نام پوشهٔ ابزار ساخت با بستهٔ ثالث packaging یکی است؛ مسیر صریح ابهام را رفع می‌کند.
SPEC = importlib.util.spec_from_file_location("windows_build", ROOT / "packaging/windows/build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def prepare(installer, bundle):
    build.verify_bundle(bundle)
    build.verify_no_secrets(bundle, build.configured_secrets())
    with installer.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    expected = installer.with_suffix(".exe.sha256").read_text(encoding="ascii").split()[0]
    if digest != expected:
        raise ValueError("هش نصب‌کننده با خروجی ساخت یکسان نیست؛ انتشار متوقف شد.")
    filename = f"RasamSetup-{__version__}.exe"
    release = {"version": __version__, "filename": filename,
               "size": installer.stat().st_size, "sha256": digest,
               "objectKey": f"releases/{__version__}/{filename}",
               "downloadPath": f"/downloads/{filename}",
               "checksumPath": f"/checksums/{filename}.sha256"}
    site = Path(__file__).resolve().parent
    (site / "release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    checksum = site / "public" / release["checksumPath"].lstrip("/")
    checksum.parent.mkdir(parents=True, exist_ok=True)
    checksum.write_text(f"{digest}  {filename}\n", encoding="ascii")
    return release


def main():
    parser = argparse.ArgumentParser(description="آماده‌سازی انتشار عمومی رصام")
    parser.add_argument("--installer", type=Path, default=ROOT / "exports/windows-build/RasamSetup.exe")
    parser.add_argument("--bundle", type=Path, default=ROOT / "exports/windows-build/dist/Rasam")
    args = parser.parse_args()
    try:
        release = prepare(args.installer, args.bundle)
        print("نسخه آمادهٔ انتشار:", release["version"], "SHA-256:", release["sha256"])
        return 0
    except Exception as error:
        print(f"انتشار آماده نشد ({type(error).__name__})؛ فایل نصب و خروجی ساخت را بررسی کنید.")
        return 1


if __name__ == "__main__":
    from rasam.console import use_utf8
    use_utf8()
    raise SystemExit(main())
