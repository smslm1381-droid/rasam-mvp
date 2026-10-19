"""همان SQL پارامتری در SQLite محلی و پل خصوصی D1 اجرا می‌شود."""

import sqlite3
import threading
from pathlib import Path

import httpx

from organization_portal.errors import PortalError


class LocalStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
        db.close()
        self.path.chmod(0o600)

    def batch(self, statements):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                db.execute("PRAGMA foreign_keys=ON")
                with db:
                    return [self._execute(db, sql, params) for sql, params in statements]
            except sqlite3.IntegrityError:
                raise PortalError("اطلاعات تکراری یا ناسازگار است؛ وضعیت را تازه کنید.", 409) from None
            except sqlite3.Error:
                raise PortalError("ذخیره یا خواندن اطلاعات ممکن نشد؛ دوباره تلاش کنید.", 503) from None
            finally:
                db.close()

    @staticmethod
    def _execute(db, sql, params):
        cursor = db.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
        return {"results": rows, "changes": max(cursor.rowcount, 0)}

    def query(self, sql, *params):
        return self.batch([(sql, params)])[0]["results"]


class RemoteStore:
    def __init__(self, url, key):
        self.url = url.rstrip("/") + "/internal/storage"
        self.key = key

    def batch(self, statements):
        body = {"statements": [{"sql": sql, "params": list(params)} for sql, params in statements]}
        try:
            response = httpx.post(self.url, json=body, headers={"Authorization": "Bearer " + self.key},
                                  timeout=20, trust_env=False, follow_redirects=False)
            if response.status_code == 409:
                raise PortalError("اطلاعات تکراری یا ناسازگار است؛ وضعیت را تازه کنید.", 409)
            response.raise_for_status()
            results = response.json()["results"]
            if not isinstance(results, list) or len(results) != len(statements):
                raise ValueError()
            return results
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise PortalError("ذخیره‌ساز مرکزی در دسترس نیست؛ دوباره تلاش کنید.", 503) from None

    def query(self, sql, *params):
        return self.batch([(sql, params)])[0]["results"]
