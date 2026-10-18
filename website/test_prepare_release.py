"""انتشار باید فایل دست‌کاری‌شده یا بستهٔ دارای راز را متوقف کند."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("prepare_release", Path(__file__).with_name("prepare_release.py"))
prepare_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_release)


@pytest.fixture
def release_files(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    for name in ["Rasam.exe", "_internal/desktop-service.json",
                 "_internal/rasam/desktop/static/index.html", "_internal/templates/customer/profile.yaml"]:
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public content", encoding="utf-8")
    installer = tmp_path / "RasamSetup.exe"
    installer.write_bytes(b"verified installer")
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    installer.with_suffix(".exe.sha256").write_text(digest, encoding="ascii")
    monkeypatch.setattr(prepare_release, "__file__", str(tmp_path / "prepare_release.py"))
    monkeypatch.setattr(prepare_release.build, "configured_secrets", lambda: ["private-test-password"])
    return installer, bundle


def test_changed_installer_is_not_published(release_files):
    installer, bundle = release_files
    installer.write_bytes(b"modified installer")
    with pytest.raises(ValueError):
        prepare_release.prepare(installer, bundle)
    assert not (installer.parent / "release.json").exists()


def test_secret_in_bundle_is_not_published(release_files):
    installer, bundle = release_files
    (bundle / "secret.txt").write_text("private-test-password", encoding="utf-8")
    with pytest.raises(ValueError):
        prepare_release.prepare(installer, bundle)
    assert not (installer.parent / "release.json").exists()


def test_release_metadata_matches_verified_installer(release_files):
    installer, bundle = release_files
    release = prepare_release.prepare(installer, bundle)
    saved = json.loads((installer.parent / "release.json").read_text(encoding="utf-8"))
    assert saved == release
    assert saved["size"] == installer.stat().st_size
    checksum = installer.parent / "public" / saved["checksumPath"].lstrip("/")
    assert checksum.read_text(encoding="ascii").split()[0] == saved["sha256"]
