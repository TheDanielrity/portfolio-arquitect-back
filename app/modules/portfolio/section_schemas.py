from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.modules.portfolio.schemas import Input, Order, Patch, Text


class SectionType(StrEnum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    GALLERY = "GALLERY"
    VIDEO = "VIDEO"
    MODEL_3D = "MODEL_3D"
    QUOTE = "QUOTE"
    SPLIT = "SPLIT"


class SectionMediaInput(Input):
    media_id: UUID
    sort_order: Order = 0
    caption: Text | None = Field(default=None, max_length=255)


class SectionMediaUpdate(Patch):
    non_nullable = frozenset({"sort_order"})
    sort_order: Order | None = None
    caption: Text | None = Field(default=None, max_length=255)


class SectionMediaResponse(SectionMediaInput):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    section_id: UUID
    created_at: datetime


def unique_media(items: list[SectionMediaInput]) -> list[SectionMediaInput]:
    if len(items) != len({item.media_id for item in items}):
        raise ValueError("Media IDs must not repeat")
    return items


class SectionCreate(Input):
    section_type: SectionType
    title: Text | None = Field(default=None, max_length=200)
    content: Text | None = Field(default=None, max_length=50000)
    sort_order: Order = 0
    is_visible: bool = True
    media: list[SectionMediaInput] = Field(default_factory=list, max_length=100)

    _unique_media = field_validator("media")(unique_media)


class SectionUpdate(Patch):
    non_nullable = frozenset({"section_type", "sort_order", "is_visible", "media"})
    section_type: SectionType | None = None
    title: Text | None = Field(default=None, max_length=200)
    content: Text | None = Field(default=None, max_length=50000)
    sort_order: Order | None = None
    is_visible: bool | None = None
    media: list[SectionMediaInput] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def check_media(self) -> Self:
        if self.media is not None:
            unique_media(self.media)
        return self


class SectionResponse(Input):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    project_id: UUID
    section_type: SectionType
    title: str | None
    content: str | None
    sort_order: int
    is_visible: bool
    created_at: datetime
    updated_at: datetime
