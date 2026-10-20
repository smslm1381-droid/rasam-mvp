"""محدودیت ورودی مستقل از فرم مرورگر است؛ خطای اعتبارسنجی هیچ راز ورودی را بازتاب نمی‌دهد."""

from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class InvitationAccept(BaseModel):
    token: SecretStr = Field(min_length=40, max_length=100)
    name: str = Field(default="", max_length=100)
    password: SecretStr = Field(default=SecretStr(""), max_length=128)


class PasswordChange(BaseModel):
    old: SecretStr = Field(max_length=128)
    new: SecretStr = Field(min_length=12, max_length=128)


class NewOrganization(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    manager_email: str = Field(min_length=3, max_length=254)
    hosts: list[str] = Field(default_factory=list, max_length=50)
    daily_limit: int = Field(default=1000, ge=1, le=100000)


class Invite(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: Literal["admin", "member"] = "member"
    daily_limit: int = Field(default=20, ge=1, le=100000)
    sources: list[str] = Field(default_factory=list, max_length=200)


class OrganizationUpdate(BaseModel):
    active: bool
    daily_limit: int = Field(ge=1, le=100000)
    hosts: list[str] = Field(max_length=50)
    manager_chat_access: bool


class MemberUpdate(BaseModel):
    active: bool
    daily_limit: int = Field(ge=1, le=100000)
    sources: list[str] = Field(max_length=200)


class ConnectionInput(BaseModel):
    db_type: Literal["mongodb", "mysql"]
    values: dict[str, str] = Field(max_length=7)
    advanced_uri: SecretStr = Field(default=SecretStr(""), max_length=4096)
    ca_pem: str = Field(default="", max_length=64000)
    sources: list[str] = Field(default_factory=list, max_length=200)
    documentation: str = Field(default="", max_length=100000)

    def connection_data(self):
        result = self.model_dump(exclude={"advanced_uri"})
        result["advanced_uri"] = self.advanced_uri.get_secret_value()
        return result


class Question(BaseModel):
    request_id: str = Field(min_length=32, max_length=64)
    question: str = Field(min_length=1, max_length=2000)
