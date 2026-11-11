from pydantic import BaseModel, ConfigDict

from app.core.validation import WebUrl
from app.modules.media.schemas import MediaType


class PublicMedia(BaseModel):
    """Delivery and presentation fields only; storage identity stays administrative."""

    model_config = ConfigDict(from_attributes=True)

    type: MediaType
    url: WebUrl
    thumbnail_url: WebUrl | None
    mime_type: str
    width: int | None
    height: int | None
    alt_text: str | None
    title: str | None
    description: str | None
