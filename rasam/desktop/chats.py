"""مسیرهای محلی گفتگو؛ انتخاب مشتری و ذخیره‌سازی در هسته انجام می‌شود."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from rasam.core.chat_store import scope_key


def _response(stored):
    if not stored.ok:
        return JSONResponse({"detail": stored.reason}, status_code=503)
    if stored.value is None or stored.value is False:
        return JSONResponse({"detail": "گفتگو پیدا نشد."}, status_code=404)
    return stored.value


def routes(app):
    router = APIRouter(prefix="/chats")

    def operate(method, *args):
        with app.state.session.lock:
            scope = scope_key()
            if not scope:
                return JSONResponse({"detail": "ابتدا اتصال دیتابیس را تنظیم کنید."}, status_code=409)
            result = getattr(app.state.session.chats, method)(scope, *args)
            if method == "delete" and result.ok and result.value:
                app.state.session.last_answer = None
                app.state.session.answer_id = None
            return _response(result)

    @router.get("")
    def listing():
        return operate("list")

    @router.post("")
    def create():
        return operate("create")

    @router.get("/{chat_id}")
    def read(chat_id: str):
        return operate("read", chat_id)

    @router.delete("/{chat_id}")
    def delete(chat_id: str):
        return operate("delete", chat_id)

    return router
