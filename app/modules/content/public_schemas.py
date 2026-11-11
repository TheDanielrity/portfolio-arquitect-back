from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

from app.core.validation import WebUrl
from app.modules.content.schemas import SettingKey
from app.modules.media.public_schemas import PublicMedia


class PublicProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_name: str
    last_name: str
    professional_title: str | None
    short_bio: str | None
    biography: str | None
    email: str | None
    phone: str | None
    location: str | None
    profile_media: PublicMedia | None
    cv_media: PublicMedia | None


class PublicSocialLink(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    url: WebUrl
    username: str | None


class PublicService(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    short_description: str | None
    description: str | None
    icon: str | None


class PublicSetting(BaseModel):
    key: SettingKey
    value: StrictStr | StrictBool
