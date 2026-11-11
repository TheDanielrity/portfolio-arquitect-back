from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContactMessage, SiteSetting
from app.modules.contact.schemas import ContactQuery


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submissions_enabled(self) -> bool:
        setting = await self.session.scalar(
            select(SiteSetting).where(SiteSetting.key == "contact_enabled")
        )
        # An absent setting preserves the default public form. Invalid legacy values fail closed.
        return setting is None or setting.value is True

    async def save(self, row: ContactMessage) -> None:
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)

    async def get(self, item_id: UUID, *, lock: bool = False) -> ContactMessage | None:
        statement = select(ContactMessage).where(ContactMessage.id == item_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list(self, query: ContactQuery) -> tuple[list[ContactMessage], int]:
        conditions = []
        if query.status is not None:
            conditions.append(ContactMessage.status == query.status.value)
        if query.q is not None:
            conditions.append(
                or_(
                    ContactMessage.name.icontains(query.q, autoescape=True),
                    ContactMessage.email.icontains(query.q, autoescape=True),
                    ContactMessage.subject.icontains(query.q, autoescape=True),
                    ContactMessage.message.icontains(query.q, autoescape=True),
                )
            )
        total = await self.session.scalar(
            select(func.count()).select_from(ContactMessage).where(*conditions)
        )
        column = {
            "created_at": ContactMessage.created_at,
            "name": func.lower(ContactMessage.name),
        }[query.sort]
        order = column.asc() if query.direction == "asc" else column.desc()
        rows = await self.session.scalars(
            select(ContactMessage)
            .where(*conditions)
            .order_by(order, ContactMessage.id.desc())
            .limit(query.limit)
            .offset(query.offset)
        )
        return list(rows), int(total or 0)

    async def now(self) -> datetime:
        value: datetime = (await self.session.execute(select(func.clock_timestamp()))).scalar_one()
        return value
