"""مسیرهای نازک HTTP راهنمای اتصال."""

from fastapi import APIRouter
from pydantic import BaseModel, Field, SecretStr
from rasam.core.connection_setup import ConnectionSetup, database_forms


class ConnectionInput(BaseModel):
    db_type: str = Field(max_length=40)
    values: dict[str, str] = Field(max_length=12)
    advanced_uri: SecretStr = Field(default=SecretStr(""), max_length=4096)


def routes():
    router = APIRouter(prefix="/setup")
    setup = ConnectionSetup()

    @router.get("/databases")
    def databases():
        return database_forms()

    @router.post("/test")
    def test(body: ConnectionInput):
        if any(len(value) > 4096 for value in body.values.values()):
            return {"ok": False, "category": "invalid", "message": "اطلاعات اتصال بیش از اندازه بلند است."}
        return setup.test(body.db_type, body.values, body.advanced_uri.get_secret_value())

    return router, setup
