"""قیمت‌های عمومی خواندنی‌اند؛ نوشتن و صدور فقط با نشست و CSRF مدیر انجام می‌شود."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin_panel import auth, mutations
from admin_panel.http import error, read_body
from admin_panel.operations import authorized
from gateway import products

router = APIRouter()


@router.get("/api/public/plans")
async def public_plans(request: Request):
    return {"plans": await products.listing(request.scope["env"].DB, public=True),
            "currency": "تومان", "payment_enabled": False}


@router.get("/api/products")
async def listing(request: Request):
    if not await auth.session(request, request.scope["env"]):
        return error("ابتدا وارد حساب مدیریت شوید.", 401)
    return {"products": await products.listing(request.scope["env"].DB)}


@router.post("/api/products/{identifier}")
async def save(identifier: str, request: Request):
    current, failure = await authorized(request)
    if failure is not None:
        return failure
    body = await read_body(request)
    try:
        result = await products.save(request.scope["env"].DB, identifier, body, current["username"])
    except ValueError as failure:
        return error(str(failure))
    return {"ok": True, "product": result} if result else error("پلن پیدا نشد.", 404)


@router.post("/api/products/{identifier}/issue")
async def issue(identifier: str, request: Request):
    current, failure = await authorized(request)
    if failure is not None:
        return failure
    db = request.scope["env"].DB
    product = await products.read(db, identifier)
    body = await read_body(request)
    if not product or not product["published"] or not product["model"]:
        return error("پلن هنوز آمادهٔ صدور نیست.")
    if set(body) != {"customer", "plan", "request_id"} or body.get("plan") not in {"monthly", "yearly"}:
        return error("اطلاعات صدور معتبر نیست.")
    if product[body["plan"] + "_price"] is None:
        return error("این دوره برای پلن عرضه نمی‌شود.")
    fields = {**body, "daily_limit": product["daily_limit"], "model": product["model"], "product_id": identifier}
    result, status = await mutations.perform(db, current["username"], "new", fields)
    return JSONResponse(result, status_code=status)
