from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.modules.media.schemas import Description, ShortText
from app.modules.media.storage import database_text, non_blank


class UploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_filename: Annotated[
        str,
        Field(min_length=1, max_length=255),
        AfterValidator(database_text),
        AfterValidator(non_blank),
    ]
    mime_type: Annotated[str, Field(min_length=3, max_length=150)]
    file_size: Annotated[int, Field(strict=True, gt=0)]
    access: Literal["private", "public"] = "private"
    alt_text: ShortText | None = None
    title: ShortText | None = None
    description: Description | None = None


class UploadResponse(BaseModel):
    upload_id: UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_at: datetime
    max_file_size: int
    provider: Literal["local", "r2"]


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: UUID
