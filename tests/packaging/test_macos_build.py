"""بررسی قابل‌اجرای ویندوز برای بستهٔ مک؛ ساخت یا امضای بومی مک را شبیه‌سازی موفق نمی‌خوانیم."""

import importlib.util
import json
from pathlib import Path
import plistlib
import struct

import pytest

PATH = Path(__file__).resolve().parents[2] / "packaging/macos/build.py"
SPEC = importlib.util.spec_from_file_location("macos_build", PATH)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def fixture_bundle(folder):
    app = folder / "Rasam.app"
    for name in ["MacOS/Rasam", "Resources/rasam.icns", "Resources/desktop-service.json",
                 "Resources/rasam/desktop/static/index.html", "Resources/templates/customer/profile.yaml"]:
        path = app / "Contents" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    with (app / "Contents/Info.plist").open("wb") as stream:
        plistlib.dump({"CFBundleExecutable": "Rasam", "CFBundleShortVersionString": build.__version__}, stream)
    return app


def test_non_macos_cannot_report_a_successful_native_build(monkeypatch, tmp_path):
    monkeypatch.setattr(build.sys, "platform", "win32")
    target = tmp_path / "output"
    assert build.main(["--gateway-url", "https://example.test", "--output", str(target)]) == 1
    assert not target.exists()


@pytest.mark.parametrize("architecture", ["arm64", "x86_64"])
def test_native_architecture_is_the_python_process_architecture(monkeypatch, architecture):
    monkeypatch.setattr(build.sys, "platform", "darwin")
    monkeypatch.setattr(build.platform, "machine", lambda: architecture)
    assert build.native_architecture() == architecture


def test_unsupported_architecture_is_rejected(monkeypatch):
    monkeypatch.setattr(build.sys, "platform", "darwin")
    monkeypatch.setattr(build.platform, "machine", lambda: "unrecognized")
    with pytest.raises(ValueError):
        build.native_architecture()


def test_build_receives_public_service_data_and_not_model_secrets(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("RASAM_LLM_API_KEY", "private-model-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "private-provider-secret")
    monkeypatch.setattr(build.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    target = tmp_path / "new"
    build.make_bundle("https://example.test", target, "arm64")
    assert json.loads((target / "desktop-service.json").read_text()) == {"gateway_url": "https://example.test"}
    environment = calls[0][1]["env"]
    assert environment["RASAM_BUILD_ARCH"] == "arm64"
    assert "RASAM_LLM_API_KEY" not in environment and "OPENAI_API_KEY" not in environment
    with pytest.raises(FileExistsError):
        build.make_bundle("https://example.test", target, "arm64")
    assert len(calls) == 1


@pytest.mark.parametrize("name", [".env", ".dev.vars", "auth.json", "chroma.sqlite3", "conversations.sqlite3", "conversations.sqlite3-journal", "customers/acme/private.txt"])
def test_customer_or_secret_files_are_rejected_from_the_app(tmp_path, name):
    app = fixture_bundle(tmp_path)
    assert build.verify_bundle(app) > 0
    path = app / "Contents/Resources" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("private")
    with pytest.raises(ValueError):
        build.verify_bundle(app)


def test_bundle_requires_real_layout_and_matching_version(tmp_path):
    app = fixture_bundle(tmp_path)
    info = app / "Contents/Info.plist"
    with info.open("wb") as stream:
        plistlib.dump({"CFBundleExecutable": "Rasam", "CFBundleShortVersionString": "0.0.0"}, stream)
    with pytest.raises(ValueError):
        build.verify_bundle(app)
    (app / "Contents/MacOS/Rasam").unlink()
    with pytest.raises(ValueError):
        build.verify_bundle(app)


def test_mac_icon_chunks_contain_png_images_at_the_declared_sizes():
    data = (PATH.parents[2] / "assets/brand/rasam.icns").read_bytes()
    assert data[:4] == b"icns" and struct.unpack_from(">I", data, 4)[0] == len(data)
    expected = {b"icp4": 16, b"icp5": 32, b"icp6": 64, b"ic07": 128,
                b"ic08": 256, b"ic09": 512, b"ic10": 1024}
    offset = 8
    seen = set()
    while offset < len(data):
        kind, size = struct.unpack_from(">4sI", data, offset)
        image = data[offset + 8:offset + size]
        assert image[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack_from(">II", image, 16) == (expected[kind], expected[kind])
        seen.add(kind)
        offset += size
    assert seen == set(expected) and offset == len(data)
