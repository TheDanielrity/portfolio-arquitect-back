from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceConflict


@asynccontextmanager
async def write_transaction(session: AsyncSession) -> AsyncIterator[None]:
    """Share the request's authentication transaction, committing only complete operations."""
    try:
        yield
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        diagnostic = getattr(exc.orig, "diag", None)
        name = getattr(diagnostic, "constraint_name", None)
        messages = {
            "pk_project_section_media": "Asset is already attached to this section",
            "uq_project_slug_active": "Project slug is already in use",
            "uq_category_slug_lower": "Category slug is already in use",
            "uq_tag_slug_lower": "Tag slug is already in use",
            "uq_tag_name_lower": "Tag name is already in use",
            "uq_project_single_featured": "Featured project changed; retry the operation",
            "uq_project_single_cover": "Project already has a cover",
            "uq_project_media_role": "Asset already has this role on the project",
        }
        if name in messages:
            raise ResourceConflict(messages[name]) from exc
        if getattr(exc.orig, "sqlstate", None) == "23503":
            raise ResourceConflict("A related resource changed; retry the operation") from exc
        raise
    except BaseException:
        await session.rollback()
        raise
