from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidOperation, ResourceConflict, ResourceNotFound
from app.models import Profile, Service, SocialLink
from app.modules.content.repository import ContentRepository
from app.modules.content.schemas import (
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
    ServiceCreate,
    ServiceQuery,
    ServiceResponse,
    ServiceUpdate,
    SocialCreate,
    SocialQuery,
    SocialResponse,
    SocialUpdate,
)
from app.modules.content.transactions import write_transaction
from app.modules.portfolio.schemas import Page, Reorder


class ContentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ContentRepository(session)

    async def _profile(self, *, lock: bool = False) -> Profile:
        row = await self.repository.profile(lock=lock)
        if row is None:
            raise ResourceNotFound("Active profile not found")
        return row

    async def _validate_media(self, body: ProfileCreate | ProfileUpdate) -> None:
        references = [(body.profile_media_id, {"IMAGE"}), (body.cv_media_id, {"PDF", "DOCUMENT"})]
        for media_id, types in sorted(references, key=lambda item: str(item[0])):
            if media_id is None:
                continue
            asset = await self.repository.asset(media_id)
            if asset is None:
                raise ResourceNotFound("Media asset not found")
            if asset.type not in types:
                raise InvalidOperation("Profile photo requires IMAGE; CV requires PDF or DOCUMENT")

    async def get_profile(self) -> ProfileResponse:
        return ProfileResponse.model_validate(await self._profile())

    async def create_profile(self, body: ProfileCreate) -> ProfileResponse:
        async with write_transaction(self.session):
            if await self.repository.profile() is not None:
                raise ResourceConflict("An active profile already exists")
            await self._validate_media(body)
            row = Profile(**body.model_dump(), is_active=True)
            await self.repository.save(row)
            response = ProfileResponse.model_validate(row)
        return response

    async def update_profile(self, body: ProfileUpdate) -> ProfileResponse:
        async with write_transaction(self.session):
            row = await self._profile(lock=True)
            await self._validate_media(body)
            for key, value in body.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            await self.repository.save(row)
            response = ProfileResponse.model_validate(row)
        return response

    async def _social(self, profile_id: UUID, item_id: UUID) -> SocialLink:
        row = await self.repository.social(profile_id, item_id)
        if row is None:
            raise ResourceNotFound("Social link not found")
        return row

    async def list_socials(self, query: SocialQuery) -> Page[SocialResponse]:
        profile = await self._profile()
        rows, total = await self.repository.socials(profile.id, query)
        return Page(
            items=[SocialResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def get_social(self, item_id: UUID) -> SocialResponse:
        profile = await self._profile()
        return SocialResponse.model_validate(await self._social(profile.id, item_id))

    async def create_social(self, body: SocialCreate) -> SocialResponse:
        async with write_transaction(self.session):
            profile = await self._profile(lock=True)
            row = SocialLink(profile_id=profile.id, **body.model_dump(mode="json"))
            await self.repository.save(row)
            response = SocialResponse.model_validate(row)
        return response

    async def update_social(self, item_id: UUID, body: SocialUpdate) -> SocialResponse:
        async with write_transaction(self.session):
            profile = await self._profile(lock=True)
            row = await self._social(profile.id, item_id)
            for key, value in body.model_dump(mode="json", exclude_unset=True).items():
                setattr(row, key, value)
            await self.repository.save(row)
            response = SocialResponse.model_validate(row)
        return response

    async def delete_social(self, item_id: UUID) -> None:
        async with write_transaction(self.session):
            profile = await self._profile(lock=True)
            await self.repository.remove(await self._social(profile.id, item_id))

    async def reorder_socials(self, body: Reorder) -> None:
        async with write_transaction(self.session):
            profile = await self._profile(lock=True)
            for item in body.items:
                row = await self._social(profile.id, item.id)
                row.sort_order = item.sort_order
                await self.repository.save(row)

    async def _service(self, item_id: UUID, *, lock: bool = False) -> Service:
        row = await self.repository.service(item_id, lock=lock)
        if row is None:
            raise ResourceNotFound("Service not found")
        return row

    async def list_services(self, query: ServiceQuery) -> Page[ServiceResponse]:
        rows, total = await self.repository.services(query)
        return Page(
            items=[ServiceResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def get_service(self, item_id: UUID) -> ServiceResponse:
        return ServiceResponse.model_validate(await self._service(item_id))

    async def create_service(self, body: ServiceCreate) -> ServiceResponse:
        async with write_transaction(self.session):
            row = Service(**body.model_dump())
            await self.repository.save(row)
            response = ServiceResponse.model_validate(row)
        return response

    async def update_service(self, item_id: UUID, body: ServiceUpdate) -> ServiceResponse:
        async with write_transaction(self.session):
            row = await self._service(item_id, lock=True)
            for key, value in body.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            await self.repository.save(row)
            response = ServiceResponse.model_validate(row)
        return response

    async def delete_service(self, item_id: UUID) -> None:
        async with write_transaction(self.session):
            await self.repository.remove(await self._service(item_id, lock=True))

    async def reorder_services(self, body: Reorder) -> None:
        async with write_transaction(self.session):
            for item in sorted(body.items, key=lambda item: item.id):
                row = await self._service(item.id, lock=True)
                row.sort_order = item.sort_order
                await self.repository.save(row)
