from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base, MediaAsset, Profile, Service, SiteSetting, SocialLink
from app.modules.content.schemas import ServiceQuery, SettingKey, SocialQuery


class ContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, row: Base) -> None:
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)

    async def remove(self, row: Base) -> None:
        await self.session.delete(row)
        await self.session.flush()

    async def profile(self, *, lock: bool = False) -> Profile | None:
        statement = select(Profile).where(Profile.is_active.is_(True))
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def asset(self, media_id: UUID) -> MediaAsset | None:
        return await self.session.scalar(
            select(MediaAsset)
            .where(MediaAsset.id == media_id)
            .with_for_update(read=True, key_share=True)
        )

    async def social(self, profile_id: UUID, item_id: UUID) -> SocialLink | None:
        return await self.session.scalar(
            select(SocialLink).where(SocialLink.profile_id == profile_id, SocialLink.id == item_id)
        )

    async def socials(self, profile_id: UUID, query: SocialQuery) -> tuple[list[SocialLink], int]:
        conditions = [SocialLink.profile_id == profile_id]
        if query.is_visible is not None:
            conditions.append(SocialLink.is_visible == query.is_visible)
        if query.q is not None:
            conditions.append(
                or_(
                    SocialLink.platform.icontains(query.q, autoescape=True),
                    SocialLink.username.icontains(query.q, autoescape=True),
                )
            )
        total = await self.session.scalar(
            select(func.count()).select_from(SocialLink).where(*conditions)
        )
        column = {
            "sort_order": SocialLink.sort_order,
            "platform": func.lower(SocialLink.platform),
            "created_at": SocialLink.created_at,
        }[query.sort]
        order = column.asc() if query.direction == "asc" else column.desc()
        rows = await self.session.scalars(
            select(SocialLink)
            .where(*conditions)
            .order_by(order, SocialLink.id)
            .limit(query.limit)
            .offset(query.offset)
        )
        return list(rows), int(total or 0)

    async def service(self, item_id: UUID, *, lock: bool = False) -> Service | None:
        statement = select(Service).where(Service.id == item_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def services(self, query: ServiceQuery) -> tuple[list[Service], int]:
        conditions = []
        if query.is_visible is not None:
            conditions.append(Service.is_visible == query.is_visible)
        if query.q is not None:
            conditions.append(
                or_(
                    Service.name.icontains(query.q, autoescape=True),
                    Service.slug.icontains(query.q, autoescape=True),
                )
            )
        total = await self.session.scalar(
            select(func.count()).select_from(Service).where(*conditions)
        )
        column = {
            "sort_order": Service.sort_order,
            "name": func.lower(Service.name),
            "created_at": Service.created_at,
        }[query.sort]
        order = column.asc() if query.direction == "asc" else column.desc()
        rows = await self.session.scalars(
            select(Service)
            .where(*conditions)
            .order_by(order, Service.id)
            .limit(query.limit)
            .offset(query.offset)
        )
        return list(rows), int(total or 0)

    async def settings(self) -> list[SiteSetting]:
        return list(
            await self.session.scalars(
                select(SiteSetting)
                .where(SiteSetting.key.in_([key.value for key in SettingKey]))
                .order_by(SiteSetting.key)
            )
        )

    async def setting(self, key: SettingKey) -> SiteSetting | None:
        return await self.session.scalar(select(SiteSetting).where(SiteSetting.key == key.value))

    async def put_setting(self, key: SettingKey, value: str | bool) -> SiteSetting:
        statement = insert(SiteSetting).values(key=key.value, value=value)
        row = await self.session.scalar(
            statement.on_conflict_do_update(
                constraint="uq_site_setting_key", set_={"value": statement.excluded.value}
            ).returning(SiteSetting),
            execution_options={"populate_existing": True},
        )
        assert row is not None
        return row
