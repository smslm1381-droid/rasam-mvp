"""نشست مدیر در D1 و رمز تصادفی قوی؛ کلید نشست و رمز خام در پایگاه نمی‌مانند."""

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit

from gateway.licenses import plain

SESSION_SECONDS = 8 * 3600
ITERATIONS = 100000


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def cookie_name(env):
    return "__Host-rasam_admin" if env.ADMIN_ORIGIN.startswith("https://") else "rasam_admin_local"


def configuration(env):
    origin = getattr(env, "ADMIN_ORIGIN", "")
    parts = urlsplit(origin)
    secure = parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost"})
    if not secure or parts.path or parts.query or parts.fragment or parts.username or not parts.hostname:
        raise ValueError("نشانی پنل معتبر نیست.")
    username = getattr(env, "ADMIN_USERNAME", "")
    encoded = getattr(env, "ADMIN_PASSWORD_HASH", "")
    algorithm, iterations, salt, expected = encoded.split("$")
    if not username or algorithm != "pbkdf2-sha256" or int(iterations) != ITERATIONS:
        raise ValueError("تنظیم مدیر آماده نیست.")
    if len(bytes.fromhex(salt)) != 16 or len(bytes.fromhex(expected)) != 32:
        raise ValueError("تنظیم رمز معتبر نیست.")
    return username, encoded


async def derive(password, salt):
    try:
        from js import Object, Uint8Array, crypto
        from pyodide.ffi import to_js
    except ImportError:
        import asyncio
        return await asyncio.to_thread(hashlib.pbkdf2_hmac, "sha256", password.encode(), salt, ITERATIONS)
    # WebCrypto محاسبه را در موتور بومی انجام می‌دهد؛ حلقهٔ پایتونی رمزنگاری نمی‌سازیم.
    raw = Uint8Array.new(to_js(list(password.encode("utf-8"))))
    key = await crypto.subtle.importKey("raw", raw, "PBKDF2", False, to_js(["deriveBits"]))
    options = to_js({"name": "PBKDF2", "salt": Uint8Array.new(to_js(list(salt))),
                     "iterations": ITERATIONS, "hash": "SHA-256"}, dict_converter=Object.fromEntries)
    return (await crypto.subtle.deriveBits(options, key, 256)).to_bytes()


async def verify(env, username, password):
    configured, encoded = configuration(env)
    _, _, salt, expected = encoded.split("$")
    actual = await derive(password, bytes.fromhex(salt))
    valid_password = hmac.compare_digest(actual.hex(), expected)
    valid_username = hmac.compare_digest(username.encode(), configured.encode())
    return valid_password and valid_username


async def reserve_login(db, address, now=None):
    now = int(time.time()) if now is None else now
    window = now // 300
    sql = """INSERT INTO admin_login_limits(bucket, window, attempts) VALUES (?, ?, 1)
        ON CONFLICT(bucket) DO UPDATE SET
        attempts = CASE WHEN window = excluded.window THEN attempts + 1 ELSE 1 END,
        window = excluded.window WHERE window <> excluded.window OR attempts < ? RETURNING attempts"""
    allowed = True
    for bucket, maximum in [("ip:" + digest(address), 5), ("global", 60)]:
        row = plain(await db.prepare(sql).bind(bucket, window, maximum).first())
        allowed = allowed and row is not None
    return allowed, 300 - now % 300


def credential_tag(env):
    username, encoded = configuration(env)
    return digest(username + ":" + encoded)


async def create_session(env, now=None):
    now = int(time.time()) if now is None else now
    token = secrets.token_urlsafe(32)
    expires = now + SESSION_SECONDS
    await env.DB.prepare("DELETE FROM admin_sessions WHERE expires_at <= ?").bind(now).run()
    await env.DB.prepare("INSERT INTO admin_sessions(token_hash, credential_tag, expires_at) VALUES (?, ?, ?)") \
        .bind(digest(token), credential_tag(env), expires).run()
    return token, expires


async def session(request, env, now=None):
    now = int(time.time()) if now is None else now
    token = request.cookies.get(cookie_name(env), "")
    if not 40 <= len(token) <= 100:
        return None
    row = plain(await env.DB.prepare("SELECT credential_tag, expires_at FROM admin_sessions WHERE token_hash = ?")
                .bind(digest(token)).first())
    if row is None or row["expires_at"] <= now or not hmac.compare_digest(row["credential_tag"], credential_tag(env)):
        return None
    return {"username": env.ADMIN_USERNAME, "csrf": digest("csrf:" + token), "expires_at": row["expires_at"]}


def valid_origin(request, env):
    return request.headers.get("Origin") == env.ADMIN_ORIGIN


def valid_csrf(request, current):
    return current is not None and hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), current["csrf"])
