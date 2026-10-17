"""HTTP انتخاب داده؛ تصمیم و نوشتن پروفایل در هسته انجام می‌شود."""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from rasam.core import desktop_onboarding


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    sources: list[str] = Field(max_length=500)
    confirmed_sensitive: list[str] = Field(default_factory=list, max_length=500)


def routes(app):
    router = APIRouter(prefix="/setup")

    @router.get("/sources")
    def sources():
        with app.state.setup.lock:
            return desktop_onboarding.inspect(app.state.setup.pending)

    @router.post("/profile")
    def profile(body: ProfileInput):
        with app.state.session.lock, app.state.setup.lock:
            result = desktop_onboarding.finish(app.state.setup.pending, body.name,
                                              body.sources, body.confirmed_sensitive)
            if result["ok"]:
                app.state.licensing.configure_runtime()
                app.state.setup.pending = None
                app.state.session.last_answer = None
                app.state.session.answer_id = None
            return result

    return router
