from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceConflict


@asynccontextmanager
async def write_transaction(session: AsyncSession) -> AsyncIterator[None]:
    """Commit the shared authenticated request transaction or roll it back completely."""
    try:
        yield
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        messages = {
            "uq_profile_single_active": "An active profile already exists",
            "uq_social_link_profile_platform": "This platform already has a social link",
            "uq_service_slug_lower": "Service slug is already in use",
        }
        if name in messages:
            raise ResourceConflict(messages[name]) from exc
        if getattr(exc.orig, "sqlstate", None) == "23503":
            raise ResourceConflict("A related resource changed; retry the operation") from exc
        raise
    except BaseException:
        await session.rollback()
        raise
