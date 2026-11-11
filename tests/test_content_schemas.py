from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import InvalidOperation
from app.modules.content.schemas import (
    ProfileCreate,
    ProfileUpdate,
    ServiceCreate,
    ServiceUpdate,
    SettingKey,
    SettingUpdate,
    SocialCreate,
    SocialUpdate,
)
from app.modules.content.settings_service import validate_setting


@pytest.mark.parametrize(
    "changes",
    [
        {"first_name": " "},
        {"last_name": ""},
        {"first_name": "x" * 101},
        {"email": "not-an-email"},
        {"email": "bad\n@example.org"},
        {"biography": "bad\x00text"},
        {"short_bio": "x" * 2001},
        {"is_active": False},
        {"profile_media_id": "invalid"},
    ],
)
def test_profile_validation(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProfileCreate.model_validate({"first_name": "Ada", "last_name": "Lima"} | changes)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///secret",
        "https://user:secret@example.org",
        "ftp://example.org",
    ],
)
def test_social_urls_reject_unsafe_schemes_and_credentials(url: str) -> None:
    with pytest.raises(ValidationError):
        SocialCreate(platform="Portfolio", url=url)


@pytest.mark.parametrize(
    "changes", [{"name": " "}, {"slug": "bad slug"}, {"icon": "<svg/>"}, {"sort_order": -1}]
)
def test_service_validation(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate({"name": "Design", "slug": "design"} | changes)


def test_patch_semantics_and_normalization() -> None:
    assert ProfileUpdate().model_dump(exclude_unset=True) == {}
    assert ProfileUpdate(cv_media_id=None).model_dump(exclude_unset=True) == {"cv_media_id": None}
    assert ServiceCreate(name=" Design ", slug=" DESIGN ").slug == "design"
    for model, field in (
        (ProfileUpdate, "first_name"),
        (ServiceUpdate, "is_visible"),
        (SocialUpdate, "url"),
    ):
        with pytest.raises(ValidationError):
            model.model_validate({field: None})
    with pytest.raises(ValidationError):
        SocialCreate.model_validate(
            {"platform": "Web", "url": "https://example.org", "profile_id": str(uuid4())}
        )


@pytest.mark.parametrize(
    "key,value",
    [
        (SettingKey.CONTACT_ENABLED, "true"),
        (SettingKey.CONTACT_ENABLED, 1),
        (SettingKey.SITE_TITLE, True),
        (SettingKey.SITE_TITLE, " "),
        (SettingKey.SITE_TITLE, "x" * 201),
        (SettingKey.SITE_DESCRIPTION, "x" * 501),
        (SettingKey.SITE_DESCRIPTION, "<script>alert(1)</script>"),
        (SettingKey.SITE_TITLE, "bad\x00text"),
        (SettingKey.SITE_TITLE, "bad\ud800"),
    ],
)
def test_settings_reject_wrong_types_markup_and_invalid_text(
    key: SettingKey, value: object
) -> None:
    with pytest.raises(InvalidOperation):
        validate_setting(key, value)


@pytest.mark.parametrize("value", [None, 1, [], {}, {"script": "bad"}])
def test_settings_do_not_accept_arbitrary_json(value: object) -> None:
    with pytest.raises(ValidationError):
        SettingUpdate.model_validate({"value": value})
