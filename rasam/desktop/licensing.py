"""HTTP محلیِ فعال‌سازی؛ کلید فقط در ورودی می‌آید و هرگز برگردانده نمی‌شود."""

from fastapi import APIRouter
from pydantic import BaseModel, Field, SecretStr


class LicenseInput(BaseModel):
    key: SecretStr = Field(min_length=20, max_length=200)


def routes(app):
    router = APIRouter(prefix="/license")

    @router.get("/status")
    def status():
        with app.state.session.lock:
            return app.state.licensing.refresh()

    @router.post("/activate")
    def activate(body: LicenseInput):
        with app.state.session.lock:
            return app.state.licensing.activate(body.key.get_secret_value())

    return router
