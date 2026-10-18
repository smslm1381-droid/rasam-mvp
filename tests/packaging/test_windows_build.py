"""خروجی ساخت نباید فایل مشتری یا راز داشته باشد؛ URL محلی نیاز به انتخاب صریح دارد."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "packaging/windows/build.py"
SPEC = importlib.util.spec_from_file_location("windows_build", PATH)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


@pytest.mark.parametrize("url", ["http://example.com", "https://u:p@example.com", "https://example.com?key=x",
                                 "https://example.com#x", "file:///private", "https://example.com/\n"])
def test_service_url_cannot_include_credentials_or_unapproved_http(url):
    with pytest.raises(ValueError):
        build.service_url(url, False)


def test_local_gateway_requires_explicit_test_build():
    with pytest.raises(ValueError):
        build.service_url("http://127.0.0.1:8787", False)
    assert build.service_url("http://127.0.0.1:8787/", True) == "http://127.0.0.1:8787"


def test_secret_scanner_catches_a_key_across_read_boundaries(tmp_path):
    secret = "private-build-test-secret"
    (tmp_path / "binary.dat").write_bytes(b"x" * (1024 * 1024 - 5) + secret.encode() + b"rest")
    with pytest.raises(ValueError):
        build.verify_no_secrets(tmp_path, [secret])
    build.verify_no_secrets(tmp_path, ["another-nonexistent-secret"])


@pytest.mark.parametrize("private_name", [".env", "conversations.sqlite3", "conversations.sqlite3-journal"])
def test_bundle_validation_rejects_customer_data(tmp_path, private_name):
    required = ["Rasam.exe", "_internal/desktop-service.json", "_internal/rasam/desktop/static/index.html",
                "_internal/templates/customer/profile.yaml"]
    for name in required:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
    assert build.verify_bundle(tmp_path) > 0
    (tmp_path / private_name).write_text("private")
    with pytest.raises(ValueError):
        build.verify_bundle(tmp_path)
