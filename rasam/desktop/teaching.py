"""مسیرهای نمایش و ذخیرهٔ دانش؛ هیچ کوئری از مرورگر پذیرفته نمی‌شود."""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from rasam.core import knowledge_editing


class FieldNote(BaseModel):
    name: str = Field(max_length=1024)
    label: str = Field(max_length=120)
    note: str = Field(max_length=2000)


class KnowledgeInput(BaseModel):
    customer: str = Field(min_length=1, max_length=64)
    fields: list[FieldNote] = Field(max_length=5000)
    documentation: str = Field(max_length=100000)


def routes(app):
    router = APIRouter()

    @router.get("/knowledge")
    def read():
        with app.state.session.lock:
            return knowledge_editing.editor_state()

    @router.put("/knowledge")
    def save(body: KnowledgeInput):
        with app.state.session.lock:
            return knowledge_editing.save([item.model_dump() for item in body.fields], body.documentation, body.customer)

    router.add_api_route("/feedback/{answer_id}/{rating}", feedback_route(app), methods=["POST"])
    return router


def feedback_route(app):
    def feedback(answer_id: str, rating: str):
        with app.state.session.lock:
            answer = app.state.session.result(answer_id)
            if rating == "positive" and app.state.session.is_followup(answer_id):
                return {"ok": False, "message": "برای نمونهٔ آموزشی، سؤال را کامل و مستقل در گفتگوی جدید بنویسید؛ این پاسخ به پیام‌های قبلی وابسته است."}
            if rating == "positive":
                return knowledge_editing.confirm_answer(answer)
            if rating == "negative":
                return knowledge_editing.count_negative(answer)
            return {"ok": False, "message": "نوع بازخورد معتبر نیست."}
    return feedback
