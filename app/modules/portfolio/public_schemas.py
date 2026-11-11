from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.media.public_schemas import PublicMedia
from app.modules.portfolio.schemas import MediaRole, PageQuery, Slug
from app.modules.portfolio.section_schemas import SectionType


class PublicProjectQuery(PageQuery):
    category: Slug | None = Field(default=None, max_length=120)
    tag: Slug | None = Field(default=None, max_length=100)


class PublicTag(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str


class PublicCategory(PublicTag):
    description: str | None


class PublicProjectCard(BaseModel):
    title: str
    slug: str
    short_description: str | None
    location: str | None
    year: int | None
    cover: PublicMedia | None
    categories: list[PublicCategory]


class PublicAttribute(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    value: str


class PublicProjectMedia(BaseModel):
    role: MediaRole
    asset: PublicMedia


class PublicSectionMedia(BaseModel):
    caption: str | None
    asset: PublicMedia


class PublicSection(BaseModel):
    section_type: SectionType
    title: str | None
    content: str | None
    media: list[PublicSectionMedia]


class PublicProjectDetail(PublicProjectCard):
    description: str | None
    area_m2: Decimal | None
    client_name: str | None
    seo_title: str | None
    seo_description: str | None
    tags: list[PublicTag]
    attributes: list[PublicAttribute]
    media: list[PublicProjectMedia]
    sections: list[PublicSection]
