from app.core.exceptions import ResourceNotFound
from app.modules.content.public_repository import PublicContentRepository
from app.modules.content.public_schemas import (
    PublicProfile,
    PublicService,
    PublicSetting,
    PublicSocialLink,
)
from app.modules.content.repository import ContentRepository
from app.modules.content.settings_service import SettingsService
from app.modules.portfolio.schemas import Page, PageQuery


class PublicContentService:
    def __init__(self, repository: PublicContentRepository) -> None:
        self.repository = repository

    async def profile(self) -> PublicProfile:
        row = await self.repository.profile()
        if row is None:
            raise ResourceNotFound("Profile not found")
        return PublicProfile.model_validate(row)

    async def services(self, query: PageQuery) -> Page[PublicService]:
        rows, total = await self.repository.services(query)
        return Page(
            items=[PublicService.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def social_links(self, query: PageQuery) -> Page[PublicSocialLink]:
        rows, total = await self.repository.social_links(query)
        return Page(
            items=[PublicSocialLink.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def settings(self) -> list[PublicSetting]:
        # Reuse the approved key allowlist and per-key validation, then remove admin fields.
        rows = await SettingsService(ContentRepository(self.repository.session)).list()
        return [PublicSetting(key=row.key, value=row.value) for row in rows]
