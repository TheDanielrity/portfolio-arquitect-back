from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.listing import Direction, Search
from app.modules.portfolio.schemas import Input, Name, PageQuery


class ContactCreate(Input):
    name: Name = Field(max_length=150)
    email: EmailStr = Field(max_length=320)
    phone: Name | None = Field(default=None, max_length=50)
    subject: Name | None = Field(default=None, max_length=200)
    message: Name = Field(max_length=10000)


class ContactReceipt(BaseModel):
    detail: Literal["Message received"] = "Message received"


class ContactStatus(StrEnum):
    NEW = "NEW"
    READ = "READ"
    REPLIED = "REPLIED"
    ARCHIVED = "ARCHIVED"
    SPAM = "SPAM"


class ContactQuery(PageQuery):
    status: ContactStatus | None = None
    q: Search | None = None
    sort: Literal["created_at", "name"] = "created_at"
    direction: Direction = "desc"


class ContactStatusUpdate(Input):
    status: Literal["READ", "REPLIED", "ARCHIVED", "SPAM"]


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    phone: str | None
    subject: str | None
    message: str
    status: ContactStatus
    created_at: datetime
    read_at: datetime | None
    replied_at: datetime | None
