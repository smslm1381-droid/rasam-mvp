"""اجرای دوم نباید سرور تازه بسازد؛ خروج فقط از مسیر احرازشده انجام می‌شود."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
import pytest

from rasam.desktop.instance import DesktopInstance

ROOT = Path(__file__).resolve().parents[2]


def test_instance_lock_and_metadata_are_released_and_invalid_url_is_rejected(tmp_path):
    first, second = DesktopInstance(tmp_path), DesktopInstance(tmp_path)
    assert first.acquire()
    assert not second.acquire()
    url = first.publish(43210, "a" * 40)
    assert url == second.read_url() == "http://127.0.0.1:43210/?token=" + "a" * 40
    (tmp_path / ".desktop-session.json").write_text(json.dumps({"port": "https://bad", "token": "x"}))
    assert second.read_url() is None
    first.close()
    assert second.acquire()
    second.close()
    assert not (tmp_path / ".desktop-session.json").exists()


def wait_for_session(process, folder):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert process.poll() is None, "برنامه پیش از آماده‌شدن متوقف شد."
        try:
            state = json.loads((folder / ".desktop-session.json").read_text())
            base = f"http://127.0.0.1:{state['port']}"
            headers = {"X-Rasam-Token": state["token"]}
            response = httpx.get(base + "/status", headers=headers, trust_env=False, timeout=1)
            if response.status_code == 200:
                return base, headers
        except (OSError, ValueError, httpx.HTTPError):
            pass
        time.sleep(0.1)
    pytest.fail("برنامه در زمان مجاز آماده نشد.")


def test_second_launch_reuses_instance_and_authenticated_exit_stops_process(tmp_path):
    env = {**os.environ, "RASAM_HOME": str(tmp_path), "RASAM_DESKTOP": "1"}
    binary = os.environ.get("RASAM_TEST_DESKTOP_EXECUTABLE")
    command = [binary, "--no-browser"] if binary else [sys.executable, str(ROOT / "rasam_desktop.py"), "--no-browser"]
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        base, headers = wait_for_session(process, tmp_path)
        second = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=20)
        assert second.returncode == 0
        assert DesktopInstance(tmp_path).read_url().startswith(base + "/")
        assert httpx.post(base + "/shutdown", trust_env=False).status_code == 401
        attack = {**headers, "Origin": "https://other.example"}
        assert httpx.post(base + "/shutdown", headers=attack, trust_env=False).status_code == 403
        response = httpx.post(base + "/shutdown", headers=headers, trust_env=False)
        assert response.status_code == 200 and response.json()["ok"]
        assert process.wait(timeout=15) == 0
        assert not (tmp_path / ".desktop-session.json").exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
