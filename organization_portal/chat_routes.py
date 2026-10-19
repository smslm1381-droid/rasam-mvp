"""مسیر گفتگو فقط خروجی سرویس دارای کنترل مالکیت را برمی‌گرداند."""

import base64
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import Response

from organization_portal import http, managed_chats
from organization_portal.errors import PortalError
from organization_portal.models import Question


def routes():
    router = APIRouter(prefix="/api/organizations/{org_id}/chats")

    @router.get("")
    def listing(request: Request, org_id: str):
        return request.app.state.chats.listing(http.current(request), org_id)

    @router.post("")
    def create(request: Request, org_id: str):
        return request.app.state.chats.create(http.current(request), org_id)

    @router.get("/{chat_id}")
    def read(request: Request, org_id: str, chat_id: str):
        return request.app.state.chats.read(http.current(request), org_id, chat_id)

    @router.delete("/{chat_id}")
    def delete(request: Request, org_id: str, chat_id: str):
        return request.app.state.chats.delete(http.current(request), org_id, chat_id)

    @router.post("/{chat_id}/ask")
    def ask(request: Request, org_id: str, chat_id: str, body: Question):
        return request.app.state.chats.ask(http.current(request), org_id, chat_id, body.request_id, body.question)

    router.include_router(export_routes())
    return router


def export_routes():
    router = APIRouter()

    @router.get("/{chat_id}/turns/{turn_id}/export/{kind}")
    def export(request: Request, org_id: str, chat_id: str, turn_id: str, kind: Literal["csv", "excel"]):
        user = http.current(request)
        chat = request.app.state.chats.read(user, org_id, chat_id)
        found = next((turn for turn in chat["turns"] if turn["id"] == turn_id), None)
        if not found or not found["answer"] or found["answer"].get("error") or not found["answer"].get("rows"):
            raise PortalError("نتیجهٔ جدولی برای خروجی موجود نیست.", 404)
        result = request.app.state.connections.engine.run({"mode": "export", "kind": kind, "rows": found["answer"]["rows"]})
        if not result.get("ok"):
            raise PortalError("ساخت خروجی کامل نشد.", 503)
        mime, suffix = ("text/csv; charset=utf-8", "csv") if kind == "csv" else (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx")
        return Response(base64.b64decode(result["content"]), media_type=mime,
                        headers={"Content-Disposition": f'attachment; filename="result.{suffix}"'})

    return router


def managed_routes():
    router = APIRouter(prefix="/api/organizations/{org_id}/managed-chats")

    @router.get("")
    def listing(request: Request, org_id: str):
        return managed_chats.listing(request.app.state.store, request.app.state.connections, http.current(request), org_id)

    @router.get("/{chat_id}")
    def read(request: Request, org_id: str, chat_id: str):
        return managed_chats.read(request.app.state.store, request.app.state.connections, http.current(request), org_id, chat_id)

    return router
