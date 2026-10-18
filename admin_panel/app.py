"""درگاه پنل خصوصی؛ داده و عملیات مدیریتی همیشه سمت سرور مجوزسنجی می‌شوند."""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from admin_panel import auth, store
from admin_panel.http import error, read_body
from admin_panel.operations import router

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router)


@app.middleware("http")
async def safe_response(request, call_next):
    try:
        response = await call_next(request)
    except (ValueError, TypeError, UnicodeError):
        response = error("اطلاعات واردشده معتبر نیست؛ مقدارها را بررسی کنید.")
    except Exception:
        response = error("پنل اکنون در دسترس نیست؛ کمی بعد دوباره تلاش کنید.", 503)
    response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
    return response


@app.get("/")
async def home(request: Request):
    env = request.scope["env"]
    auth.configuration(env)
    if await auth.session(request, env):
        return RedirectResponse("/panel", status_code=303)
    asset = await env.ASSETS.fetch(env.ADMIN_ORIGIN + "/index.html")
    return HTMLResponse(await asset.text())


@app.get("/panel")
@app.get("/panel.html")
async def panel(request: Request):
    env = request.scope["env"]
    if not await auth.session(request, env):
        return RedirectResponse("/", status_code=303)
    asset = await env.ASSETS.fetch(env.ADMIN_ORIGIN + "/panel.html")
    return HTMLResponse(await asset.text())


@app.post("/api/login")
async def login(request: Request):
    env = request.scope["env"]
    auth.configuration(env)
    if not auth.valid_origin(request, env):
        return error("درخواست ورود از این نشانی مجاز نیست.", 403)
    body = await read_body(request)
    username, password = body.get("username"), body.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 254 or not 1 <= len(password) <= 256:
        return error("نام کاربری یا رمز عبور درست نیست.", 401)
    allowed, retry = await auth.reserve_login(env.DB, request.headers.get("CF-Connecting-IP", "unknown"))
    if not allowed:
        response = error("تلاش‌های ورود زیاد است؛ چند دقیقه بعد دوباره امتحان کنید.", 429)
        response.headers["Retry-After"] = str(retry)
        return response
    if not await auth.verify(env, username, password):
        return error("نام کاربری یا رمز عبور درست نیست.", 401)
    token, expires = await auth.create_session(env)
    response = JSONResponse({"ok": True, "expires_at": expires})
    response.set_cookie(auth.cookie_name(env), token, max_age=auth.SESSION_SECONDS,
                        secure=env.ADMIN_ORIGIN.startswith("https://"), httponly=True, samesite="strict", path="/")
    return response


@app.get("/api/me")
async def me(request: Request):
    current = await auth.session(request, request.scope["env"])
    return JSONResponse(current) if current else error("ابتدا وارد حساب مدیریت شوید.", 401)


@app.post("/api/logout")
async def logout(request: Request):
    env = request.scope["env"]
    current = await auth.session(request, env)
    if not auth.valid_origin(request, env) or not auth.valid_csrf(request, current):
        return error("درخواست خروج معتبر نیست؛ صفحه را دوباره باز کنید.", 403)
    token = request.cookies.get(auth.cookie_name(env), "")
    await env.DB.prepare("DELETE FROM admin_sessions WHERE token_hash = ?").bind(auth.digest(token)).run()
    response = JSONResponse({"ok": True})
    response.delete_cookie(auth.cookie_name(env), secure=env.ADMIN_ORIGIN.startswith("https://"),
                           httponly=True, samesite="strict", path="/")
    return response


@app.get("/api/licenses")
async def licenses(request: Request):
    env = request.scope["env"]
    if not await auth.session(request, env):
        return error("ابتدا وارد حساب مدیریت شوید.", 401)
    values = request.query_params
    result = await store.listing(env.DB, values.get("search", ""), values.get("status", "all"), int(values.get("page", "1")))
    return JSONResponse(result)


@app.get("/{asset:path}")
async def public_asset(asset: str, request: Request):
    # همهٔ مسیرها اول به برنامه می‌رسند تا aliasهای فایل HTML از مجوزسنجی عبور نکنند.
    allowed = {"index.html", "admin.js", "actions.js", "style.css", "fonts/Vazirmatn-33.003.woff2",
               "fonts/OFL.txt", "fonts/README.txt"}
    if asset not in allowed:
        return error("این صفحه پیدا نشد.", 404)
    env = request.scope["env"]
    result = await env.ASSETS.fetch(env.ADMIN_ORIGIN + "/" + asset)
    body = await result.bytes()
    return Response(body, media_type=result.headers.get("Content-Type"))
