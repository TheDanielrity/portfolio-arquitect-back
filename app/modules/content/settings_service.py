from app.core.exceptions import InvalidOperation, ResourceNotFound
from app.models import SiteSetting
from app.modules.content.repository import ContentRepository
from app.modules.content.schemas import SettingKey, SettingResponse, SettingUpdate
from app.modules.content.transactions import write_transaction
from app.modules.media.storage import database_text


def validate_setting(key: SettingKey, value: object) -> str | bool:
    """Only explicitly supported presentation values enter or leave the settings API."""
    if key == SettingKey.CONTACT_ENABLED:
        if type(value) is not bool:
            raise InvalidOperation("contact_enabled requires a boolean")
        return value
    limit = 200 if key == SettingKey.SITE_TITLE else 500
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise InvalidOperation(f"Setting requires nonblank text of at most {limit} characters")
    if any(character in value for character in "<>") or any(
        ord(character) < 32 for character in value
    ):
        raise InvalidOperation("Settings accept plain text without markup or control characters")
    try:
        database_text(value)
    except ValueError as exc:
        raise InvalidOperation("Setting contains invalid text") from exc
    return value


class SettingsService:
    def __init__(self, repository: ContentRepository) -> None:
        self.repository = repository

    def _response(self, row: SiteSetting) -> SettingResponse:
        key = SettingKey(row.key)
        return SettingResponse(
            key=key, value=validate_setting(key, row.value), updated_at=row.updated_at
        )

    async def list(self) -> list[SettingResponse]:
        # The allowlist bounds this collection to three records, including legacy databases.
        return [self._response(row) for row in await self.repository.settings()]

    async def get(self, key: SettingKey) -> SettingResponse:
        row = await self.repository.setting(key)
        if row is None:
            raise ResourceNotFound("Site setting not configured")
        return self._response(row)

    async def put(self, key: SettingKey, body: SettingUpdate) -> SettingResponse:
        value = validate_setting(key, body.value)
        async with write_transaction(self.repository.session):
            row = await self.repository.put_setting(key, value)
            response = self._response(row)
        return response
