import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
)

from app.core.validation import database_text

Text = Annotated[str, AfterValidator(database_text)]


def valid_password(value: SecretStr) -> SecretStr:
    try:
        value.get_secret_value().encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Password must contain valid Unicode") from exc
    return value


Password = Annotated[SecretStr, AfterValidator(valid_password)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Annotated[Text, StringConstraints(strip_whitespace=True, min_length=1, max_length=320)]
    password: Password = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: SecretStr = Field(min_length=64, max_length=64)

    @field_validator("refresh_token")
    @classmethod
    def validate_token_format(cls, value: SecretStr) -> SecretStr:
        if re.fullmatch(r"[A-Za-z0-9_-]{64}", value.get_secret_value()) is None:
            raise ValueError("Invalid refresh token format")
        return value


class TokenResponse(BaseModel):
    access_token: str = Field(repr=False)
    refresh_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool


class AdministratorCreate(BaseModel):
    """Input for local provisioning only; never accepted by a public API route."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[Text, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]
    first_name: Annotated[
        Text, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    last_name: Annotated[
        Text, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    password: Password = Field(min_length=12, max_length=1024)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        # Provisioning requires a basic mailbox shape, not DNS verification.
        if re.fullmatch(r"[^\s@]+@[^\s@]+", value) is None:
            raise ValueError("Enter an email address")
        return value
