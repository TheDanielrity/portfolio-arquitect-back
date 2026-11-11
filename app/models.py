"""Import this registry before using ORM models or Alembic metadata."""

from app.core.database import Base as Base
from app.modules.auth.models import AppUser, RefreshToken
from app.modules.contact.models import ContactMessage
from app.modules.content.models import Profile, Service, SiteSetting, SocialLink
from app.modules.media.models import MediaAsset
from app.modules.media.operation_models import StorageOperation
from app.modules.portfolio.models import (
    Category,
    Project,
    ProjectAttribute,
    ProjectCategory,
    ProjectMedia,
    ProjectSection,
    ProjectSectionMedia,
    ProjectTag,
    Tag,
)

__all__ = [
    "StorageOperation",
    "AppUser",
    "RefreshToken",
    "MediaAsset",
    "Project",
    "Category",
    "ProjectCategory",
    "Tag",
    "ProjectTag",
    "ProjectAttribute",
    "ProjectMedia",
    "ProjectSection",
    "ProjectSectionMedia",
    "Profile",
    "SocialLink",
    "Service",
    "SiteSetting",
    "ContactMessage",
]
