from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StrictBool, StrictStr

from app.core.listing import Direction, Search
from app.core.validation import WebUrl
from app.modules.portfolio.schemas import Input, Name, Order, PageQuery, Patch, Slug, Text


class ServiceQuery(PageQuery):
    q: Search | None = None
    is_visible: bool | None = None
    sort: Literal["sort_order", "name", "created_at"] = "sort_order"
    direction: Direction = "asc"


class SocialQuery(PageQuery):
    q: Search | None = None
    is_visible: bool | None = None
    sort: Literal["sort_order", "platform", "created_at"] = "sort_order"
    direction: Direction = "asc"


Email = Annotated[Name, Field(max_length=320, pattern=r"^[^\s@]+@[^\s@]+$")]
Icon = Annotated[str, Field(max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")]


class ProfileCreate(Input):
    first_name: Name = Field(max_length=100)
    last_name: Name = Field(max_length=100)
    professional_title: Text | None = Field(default=None, max_length=150)
    short_bio: Text | None = Field(default=None, max_length=2000)
    biography: Text | None = Field(default=None, max_length=50000)
    email: Email | None = None
    phone: Text | None = Field(default=None, max_length=50)
    location: Text | None = Field(default=None, max_length=200)
    profile_media_id: UUID | None = None
    cv_media_id: UUID | None = None


class ProfileUpdate(Patch):
    non_nullable = frozenset({"first_name", "last_name"})
    first_name: Name | None = Field(default=None, max_length=100)
    last_name: Name | None = Field(default=None, max_length=100)
    professional_title: Text | None = Field(default=None, max_length=150)
    short_bio: Text | None = Field(default=None, max_length=2000)
    biography: Text | None = Field(default=None, max_length=50000)
    email: Email | None = None
    phone: Text | None = Field(default=None, max_length=50)
    location: Text | None = Field(default=None, max_length=200)
    profile_media_id: UUID | None = None
    cv_media_id: UUID | None = None


class ProfileResponse(ProfileCreate):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SocialCreate(Input):
    platform: Name = Field(max_length=50)
    url: WebUrl
    username: Text | None = Field(default=None, max_length=100)
    sort_order: Order = 0
    is_visible: bool = True


class SocialUpdate(Patch):
    non_nullable = frozenset({"platform", "url", "sort_order", "is_visible"})
    platform: Name | None = Field(default=None, max_length=50)
    url: WebUrl | None = None
    username: Text | None = Field(default=None, max_length=100)
    sort_order: Order | None = None
    is_visible: bool | None = None


class SocialResponse(SocialCreate):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    profile_id: UUID
    created_at: datetime
    updated_at: datetime


class ServiceCreate(Input):
    name: Name = Field(max_length=150)
    slug: Slug = Field(max_length=170)
    short_description: Text | None = Field(default=None, max_length=300)
    description: Text | None = Field(default=None, max_length=20000)
    icon: Icon | None = None
    sort_order: Order = 0
    is_visible: bool = True


class ServiceUpdate(Patch):
    non_nullable = frozenset({"name", "slug", "sort_order", "is_visible"})
    name: Name | None = Field(default=None, max_length=150)
    slug: Slug | None = Field(default=None, max_length=170)
    short_description: Text | None = Field(default=None, max_length=300)
    description: Text | None = Field(default=None, max_length=20000)
    icon: Icon | None = None
    sort_order: Order | None = None
    is_visible: bool | None = None


class ServiceResponse(ServiceCreate):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    created_at: datetime
    updated_at: datetime


class SettingKey(StrEnum):
    SITE_TITLE = "site_title"
    SITE_DESCRIPTION = "site_description"
    CONTACT_ENABLED = "contact_enabled"


class SettingUpdate(Input):
    value: StrictStr | StrictBool


class SettingResponse(SettingUpdate):
    key: SettingKey
    updated_at: datetime
