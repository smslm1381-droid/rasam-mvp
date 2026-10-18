"""ساخت بومی مک؛ هر معماری با Python و وابستگی‌های همان معماری ساخته می‌شود."""

import argparse
import hashlib
import json
import platform
import plistlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rasam import __version__
from scripts.desktop_build_support import service_url, clean_environment, verify_no_secrets, configured_secrets


def native_architecture():
    if sys.platform != "darwin":
        raise ValueError("ساخت نهایی مک باید روی macOS انجام شود؛ ویندوز خروجی مک نمی‌سازد.")
    architecture = platform.machine()
    if architecture not in {"arm64", "x86_64"}:
        raise ValueError("این معماری برای نسخهٔ مک پشتیبانی نمی‌شود.")
    return architecture


def make_bundle(url, output, architecture):
    output.mkdir(parents=True, exist_ok=False)
    service = output / "desktop-service.json"
    service.write_text(json.dumps({"gateway_url": url}), encoding="utf-8")
    env = {**clean_environment(), "RASAM_BUILD_SERVICE_FILE": str(service),
           "RASAM_BUILD_ARCH": architecture, "RASAM_BUILD_VERSION": __version__}
    subprocess.run([sys.executable, "-m", "PyInstaller", str(ROOT / "packaging/macos/rasam.spec"),
                    "--distpath", str(output / "dist"), "--workpath", str(output / "work"),
                    "--noconfirm"], cwd=ROOT, env=env, check=True)
    return output / "dist/Rasam.app"


def verify_bundle(bundle):
    resources = bundle / "Contents/Resources"
    required = [bundle / "Contents/MacOS/Rasam", bundle / "Contents/Info.plist",
                resources / "rasam.icns", resources / "desktop-service.json",
                resources / "rasam/desktop/static/index.html", resources / "templates/customer/profile.yaml"]
    if not all(path.is_file() for path in required):
        raise ValueError("بستهٔ مک ناقص است.")
    with (bundle / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info.get("CFBundleShortVersionString") != __version__ or info.get("CFBundleExecutable") != "Rasam":
        raise ValueError("نسخه یا فایل اجرای بستهٔ مک معتبر نیست.")
    for path in bundle.rglob("*"):
        if path.is_symlink() and not path.resolve().is_relative_to(bundle.resolve()):
            raise ValueError("پیوند بیرون از بستهٔ مک مجاز نیست.")
        if path.is_file() and (path.name in {".env", ".dev.vars", "auth.json", "chroma.sqlite3"}
                              or "customers" in path.relative_to(bundle).parts):
            raise ValueError("دادهٔ مشتری یا فایل راز در بسته پیدا شد.")
    return sum(path.stat().st_size for path in bundle.rglob("*") if path.is_file())


def make_dmg(bundle, output, architecture):
    staging = output / "dmg"
    staging.mkdir()
    shutil.copytree(bundle, staging / "Rasam.app", symlinks=True)
    (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
    shutil.copyfile(ROOT / "packaging/macos/INSTALL.txt", staging / "INSTALL.txt")
    target = output / f"Rasam-{__version__}-macOS-{architecture}.dmg"
    subprocess.run(["hdiutil", "create", "-volname", "Rasam", "-srcfolder", str(staging),
                    "-format", "UDZO", str(target)], check=True)
    subprocess.run(["hdiutil", "verify", str(target)], check=True)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    target.with_suffix(".dmg.sha256").write_text(digest + "  " + target.name + "\n", encoding="ascii")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="ساخت برنامه و دیسک نصب رصام برای مک")
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--local-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        architecture = native_architecture()
        url = service_url(args.gateway_url, args.local_test)
        output = (args.output or ROOT / f"exports/macos-{__version__}-{architecture}").resolve()
        bundle = make_bundle(url, output, architecture)
        size = verify_bundle(bundle)
        verify_no_secrets(bundle, configured_secrets())
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
        image = make_dmg(bundle, output, architecture)
        report = {"version": __version__, "architecture": architecture, "build_host": platform.mac_ver()[0],
                  "signing": "ad-hoc", "notarized": False, "bundle_bytes": size, "image": image.name}
        (output / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("بستهٔ آزمایشی مک ساخته و امضای فنی آن بررسی شد؛ پذیرش روی دستگاه مقصد هنوز لازم است.")
        print(image)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ساخت مک کامل نشد ({type(error).__name__})؛ محیط macOS و خروجی ابزار ساخت را بررسی کنید.")
        return 1


if __name__ == "__main__":
    from rasam.console import use_utf8
    use_utf8()
    raise SystemExit(main())
