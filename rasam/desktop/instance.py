"""قفل سیستم‌عامل با پایان فرایند آزاد می‌شود؛ فایل مانده به‌تنهایی قفل نیست."""

import json
import os
import re
import time
from pathlib import Path


class DesktopInstance:
    def __init__(self, home: Path):
        self.home = home
        self.stream = None
        self.owned = False

    def acquire(self) -> bool:
        self.home.mkdir(parents=True, exist_ok=True)
        self.stream = (self.home / ".desktop.lock").open("a+b")
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            self.stream = None
            return False
        self.owned = True
        (self.home / ".desktop-session.json").unlink(missing_ok=True)
        return True

    def publish(self, port: int, token: str) -> str:
        state = {"port": port, "token": token}
        path = self.home / ".desktop-session.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        temporary.replace(path)
        return self.read_url()

    def read_url(self) -> str | None:
        try:
            state = json.loads((self.home / ".desktop-session.json").read_text(encoding="utf-8"))
            port, token = state["port"], state["token"]
            if type(port) is not int or not 1 <= port <= 65535:
                return None
            if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
                return None
            return f"http://127.0.0.1:{port}/?token={token}"
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def wait_url(self) -> str | None:
        for _ in range(30):
            if url := self.read_url():
                return url
            time.sleep(0.1)
        return None

    def close(self):
        if self.owned:
            (self.home / ".desktop-session.json").unlink(missing_ok=True)
        if self.stream is not None:
            self.stream.close()
        self.stream = None
        self.owned = False
