from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    GetJsonSchemaHandler,
    StringConstraints,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from app.core.listing import Direction, Search
from app.modules.media.storage import database_text, non_blank


def normalize_slug(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


Text = Annotated[str, AfterValidator(database_text)]
Name = Annotated[
    Text, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(non_blank)
]
Slug = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$"), BeforeValidator(normalize_slug)
]
Order = Annotated[int, Field(strict=True, ge=0, le=2147483647)]
Area = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]
Year = Annotated[int, Field(strict=True, ge=1800, le=2200)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Patch(Input):
    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        result = handler.resolve_ref_schema(handler(schema))
        # Omission uses None internally; explicit null remains forbidden by the validator.
        for name in cls.non_nullable:
            field = result["properties"][name]
            alternatives = [item for item in field.pop("anyOf") if item.get("type") != "null"]
            if len(alternatives) == 1:
                field.update(alternatives[0])
            else:
                field["anyOf"] = alternatives
            field.pop("default", None)
        return result

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        for field in self.model_fields_set & self.non_nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PageQuery(Input):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=9223372036854775807)


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class ProjectStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class Visibility(StrEnum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    UNLISTED = "UNLISTED"


class MediaRole(StrEnum):
    COVER = "COVER"
    GALLERY = "GALLERY"
    PLAN = "PLAN"
    RENDER = "RENDER"
    DOCUMENT = "DOCUMENT"
    MODEL = "MODEL"


class ProjectCreate(Input):
    title: Name = Field(max_length=200)
    slug: Slug = Field(max_length=220)
    short_description: Text | None = Field(default=None, max_length=500)
    description: Text | None = Field(default=None, max_length=50000)
    location: Text | None = Field(default=None, max_length=255)
    year: Year | None = None
    area_m2: Area | None = None
    client_name: Text | None = Field(default=None, max_length=200)
    status: ProjectStatus = ProjectStatus.DRAFT
    visibility: Visibility = Visibility.PUBLIC
    is_featured: bool = Field(
        default=False,
        description="Selecting true atomically replaces the previous featured project. "
        "Only published, public projects appear on the homepage.",
    )
    sort_order: Order = 0
    seo_title: Text | None = Field(default=None, max_length=200)
    seo_description: Text | None = Field(default=None, max_length=320)


class ProjectUpdate(Patch):
    non_nullable = frozenset({"title", "slug", "status", "visibility", "is_featured", "sort_order"})
    title: Name | None = Field(default=None, max_length=200)
    slug: Slug | None = Field(default=None, max_length=220)
    short_description: Text | None = Field(default=None, max_length=500)
    description: Text | None = Field(default=None, max_length=50000)
    location: Text | None = Field(default=None, max_length=255)
    year: Year | None = None
    area_m2: Area | None = None
    client_name: Text | None = Field(default=None, max_length=200)
    status: ProjectStatus | None = None
    visibility: Visibility | None = None
    is_featured: bool | None = Field(
        default=None,
        description="Selecting true atomically replaces the previous featured project. "
        "Only published, public projects appear on the homepage.",
    )
    sort_order: Order | None = None
    seo_title: Text | None = Field(default=None, max_length=200)
    seo_description: Text | None = Field(default=None, max_length=320)


class ProjectResponse(ProjectCreate):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectQuery(PageQuery):
    q: Search | None = None
    sort: Literal["sort_order", "title", "created_at", "updated_at"] = "sort_order"
    direction: Direction = "asc"
    status: ProjectStatus | None = None
    visibility: Visibility | None = None
    is_featured: bool | None = None
    category_id: UUID | None = None
    tag_id: UUID | None = None


class TagQuery(PageQuery):
    q: Search | None = None
    sort: Literal["name", "created_at"] = "name"
    direction: Direction = "asc"


class CategoryQuery(PageQuery):
    q: Search | None = None
    is_active: bool | None = None
    sort: Literal["sort_order", "name", "created_at"] = "sort_order"
    direction: Direction = "asc"


class CategoryCreate(Input):
    name: Name = Field(max_length=100)
    slug: Slug = Field(max_length=120)
    description: Text | None = Field(default=None, max_length=20000)
    sort_order: Order = 0
    is_active: bool = True


class CategoryUpdate(Patch):
    non_nullable = frozenset({"name", "slug", "sort_order", "is_active"})
    name: Name | None = Field(default=None, max_length=100)
    slug: Slug | None = Field(default=None, max_length=120)
    description: Text | None = Field(default=None, max_length=20000)
    sort_order: Order | None = None
    is_active: bool | None = None


class CategoryResponse(CategoryCreate):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    created_at: datetime
    updated_at: datetime


class TagCreate(Input):
    name: Name = Field(max_length=80)
    slug: Slug = Field(max_length=100)


class TagUpdate(Patch):
    non_nullable = frozenset({"name", "slug"})
    name: Name | None = Field(default=None, max_length=80)
    slug: Slug | None = Field(default=None, max_length=100)


class TagResponse(TagCreate):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    created_at: datetime


class Assignment(Input):
    ids: list[UUID] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len(self.ids) != len(set(self.ids)):
            raise ValueError("IDs must not repeat")
        return self


class OrderItem(Input):
    id: UUID
    sort_order: Order


class Reorder(Input):
    items: list[OrderItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len(self.items) != len({item.id for item in self.items}):
            raise ValueError("IDs must not repeat")
        return self


class AttributeCreate(Input):
    label: Name = Field(max_length=100)
    value: Name = Field(max_length=500)
    sort_order: Order = 0


class AttributeUpdate(Patch):
    non_nullable = frozenset({"label", "value", "sort_order"})
    label: Name | None = Field(default=None, max_length=100)
    value: Name | None = Field(default=None, max_length=500)
    sort_order: Order | None = None


class AttributeResponse(AttributeCreate):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime


class MediaAttach(Input):
    media_id: UUID
    role: MediaRole
    sort_order: Order = 0


class MediaLinkUpdate(Patch):
    non_nullable = frozenset({"role", "sort_order"})
    role: MediaRole | None = None
    sort_order: Order | None = None


class MediaLinkResponse(MediaAttach):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    project_id: UUID
    created_at: datetime


class CoverSelection(Input):
    media_id: UUID
