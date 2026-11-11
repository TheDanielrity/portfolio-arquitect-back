from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Profile, Service, SocialLink
from app.modules.portfolio.schemas import PageQuery


class PublicContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def profile(self) -> Profile | None:
        return await self.session.scalar(
            select(Profile)
            .where(Profile.is_active.is_(True))
            .options(joinedload(Profile.profile_media), joinedload(Profile.cv_media))
        )

    async def _page[T](self, statement: Select[T], query: PageQuery) -> tuple[list[T], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        rows = await self.session.scalars(statement.limit(query.limit).offset(query.offset))
        return list(rows), int(total or 0)

    async def services(self, query: PageQuery) -> tuple[list[Service], int]:
        return await self._page(
            select(Service)
            .where(Service.is_visible.is_(True))
            .order_by(Service.sort_order, Service.slug),
            query,
        )

    async def social_links(self, query: PageQuery) -> tuple[list[SocialLink], int]:
        return await self._page(
            select(SocialLink)
            .join(Profile, SocialLink.profile_id == Profile.id)
            .where(Profile.is_active.is_(True), SocialLink.is_visible.is_(True))
            .order_by(SocialLink.sort_order, SocialLink.id),
            query,
        )
