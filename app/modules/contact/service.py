from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidOperation, ResourceNotFound
from app.models import ContactMessage
from app.modules.contact.dependencies import SubmissionContext
from app.modules.contact.repository import ContactRepository
from app.modules.contact.schemas import (
    ContactCreate,
    ContactQuery,
    ContactReceipt,
    ContactResponse,
    ContactStatusUpdate,
)
from app.modules.portfolio.schemas import Page


class ContactService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ContactRepository(session)

    async def submit(self, body: ContactCreate, context: SubmissionContext) -> ContactReceipt:
        try:
            if not await self.repository.submissions_enabled():
                raise InvalidOperation("Contact submissions are disabled")
            row = ContactMessage(
                **body.model_dump(),
                status="NEW",
                ip_address=context.ip_address,
                user_agent=context.user_agent,
            )
            await self.repository.save(row)
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise
        return ContactReceipt()

    async def _get(self, item_id: UUID, *, lock: bool = False) -> ContactMessage:
        row = await self.repository.get(item_id, lock=lock)
        if row is None:
            raise ResourceNotFound("Contact message not found")
        return row

    async def get(self, item_id: UUID) -> ContactResponse:
        return ContactResponse.model_validate(await self._get(item_id))

    async def list(self, query: ContactQuery) -> Page[ContactResponse]:
        rows, total = await self.repository.list(query)
        return Page(
            items=[ContactResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def set_status(self, item_id: UUID, body: ContactStatusUpdate) -> ContactResponse:
        """Reclassify a message while preserving its first read/reply timestamps."""
        try:
            row = await self._get(item_id, lock=True)
            now = max(await self.repository.now(), row.created_at)
            if body.status in {"READ", "REPLIED"} and row.read_at is None:
                row.read_at = now
            if body.status == "REPLIED" and row.replied_at is None:
                row.replied_at = now
            row.status = body.status
            await self.repository.save(row)
            response = ContactResponse.model_validate(row)
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise
        return response
