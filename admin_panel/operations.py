"""مسیرهای تغییر لایسنس؛ نشست، Origin و CSRF پیش از تماس با منطق تغییر بررسی می‌شوند."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin_panel import auth, mutations
from admin_panel.http import read_body

router = APIRouter()


async def authorized(request):
    env = request.scope["env"]
    current = await auth.session(request, env)
    if current is None:
        return None, JSONResponse({"ok": False, "message": "ابتدا وارد حساب مدیریت شوید."}, status_code=401)
    if not auth.valid_origin(request, env) or not auth.valid_csrf(request, current):
        return None, JSONResponse({"ok": False, "message": "درخواست معتبر نیست؛ صفحه را دوباره باز کنید."}, status_code=403)
    return current, None


async def execute(request, action, identifier=None):
    current, failure = await authorized(request)
    if failure is not None:
        return failure
    body = await read_body(request)
    result, status = await mutations.perform(request.scope["env"].DB, current["username"], action, body, identifier)
    return JSONResponse(result, status_code=status)


@router.post("/api/licenses/new")
async def issue(request: Request):
    return await execute(request, "new")


@router.post("/api/licenses/{identifier}/{action}")
async def change(identifier: str, action: str, request: Request):
    if action not in {"extend", "revoke", "quota"}:
        return JSONResponse({"ok": False, "message": "این عملیات وجود ندارد."}, status_code=404)
    return await execute(request, action, identifier)


@router.get("/api/events")
async def events(request: Request):
    env = request.scope["env"]
    if not await auth.session(request, env):
        return JSONResponse({"ok": False, "message": "ابتدا وارد حساب مدیریت شوید."}, status_code=401)
    return JSONResponse(await mutations.recent(env.DB))
