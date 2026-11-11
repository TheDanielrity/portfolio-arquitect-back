"""Legacy metadata registration location; storage operations use StoragePort."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.core.validation import WebUrl
from app.core.validation import database_text as database_text


def non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("Text must not be blank")
    return value


class StorageLocation(BaseModel):
    """Object identity returned by an adapter and accepted when registering metadata."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    storage_provider: Annotated[
        str,
        StringConstraints(min_length=1, max_length=50),
        AfterValidator(database_text),
        AfterValidator(non_blank),
    ]
    storage_key: Annotated[
        str,
        StringConstraints(min_length=1, max_length=500),
        AfterValidator(database_text),
        AfterValidator(non_blank),
    ]
    url: WebUrl
    thumbnail_url: WebUrl | None = None
