import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
)

from app.core.listing import Direction, Search
from app.modules.media.storage import StorageLocation, database_text, non_blank


class MediaType(StrEnum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    PDF = "PDF"
    MODEL_3D = "MODEL_3D"
    DOCUMENT = "DOCUMENT"


def validate_metadata(value: dict[str, JsonValue] | None) -> dict[str, JsonValue] | None:
    if value is None:
        return value
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        database_text(encoded)
        if "\\u0000" in encoded:
            # Inspect decoded strings to distinguish NUL from a literal backslash sequence.
            def check(item: JsonValue) -> None:
                if isinstance(item, str):
                    database_text(item)
                elif isinstance(item, list):
                    for child in item:
                        check(child)
                elif isinstance(item, dict):
                    for key, child in item.items():
                        database_text(key)
                        check(child)

            check(value)
        if len(encoded.encode("utf-8")) > 65536:
            raise ValueError("Metadata must not exceed 64 KiB of JSON")
    except (UnicodeEncodeError, RecursionError) as exc:
        raise ValueError("Invalid metadata") from exc
    return value


ShortText = Annotated[str, StringConstraints(max_length=255), AfterValidator(database_text)]
Description = Annotated[str, StringConstraints(max_length=20000), AfterValidator(database_text)]
Metadata = Annotated[dict[str, JsonValue] | None, AfterValidator(validate_metadata)]
Dimension = Annotated[int, Field(strict=True, gt=0, le=2147483647)]


class MediaCreate(StorageLocation):
    type: MediaType
    original_filename: Annotated[
        str,
        StringConstraints(min_length=1, max_length=255),
        AfterValidator(database_text),
        AfterValidator(non_blank),
    ]
    mime_type: Annotated[
        str,
        StringConstraints(
            min_length=3, max_length=150, pattern=r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$"
        ),
    ]
    file_size: Annotated[int, Field(strict=True, ge=0, le=9223372036854775807)]
    width: Dimension | None = None
    height: Dimension | None = None
    alt_text: ShortText | None = None
    title: ShortText | None = None
    description: Description | None = None
    metadata: Metadata = None

    @field_validator("mime_type")
    @classmethod
    def normalize_mime_type(cls, value: str) -> str:
        return value.lower()


class MediaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    alt_text: ShortText | None = None
    title: ShortText | None = None
    description: Description | None = None
    metadata: Metadata = None


class MediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: MediaType
    original_filename: str
    storage_provider: str
    storage_key: str
    url: str
    thumbnail_url: str | None
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    alt_text: str | None
    title: str | None
    description: str | None
    metadata: dict[str, JsonValue] | None = Field(validation_alias="asset_metadata")
    created_at: datetime
    updated_at: datetime


class MediaListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=9223372036854775807)
    type: MediaType | None = None
    q: Search | None = None
    sort: Literal["created_at", "original_filename", "file_size"] = "created_at"
    direction: Direction = "desc"


class MediaPage(BaseModel):
    items: list[MediaResponse]
    total: int
    limit: int
    offset: int
