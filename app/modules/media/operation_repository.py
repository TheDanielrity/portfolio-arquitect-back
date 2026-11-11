from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MediaAsset,
    Profile,
    Project,
    ProjectMedia,
    ProjectSection,
    ProjectSectionMedia,
)
from app.modules.media.operation_models import StorageOperation


class OperationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, operation_id: UUID) -> StorageOperation | None:
        return await self.session.scalar(
            select(StorageOperation)
            .where(StorageOperation.id == operation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def deletion(self, asset_id: UUID) -> StorageOperation | None:
        return await self.session.scalar(
            select(StorageOperation)
            .where(StorageOperation.media_id == asset_id, StorageOperation.kind == "DELETE")
            .order_by(StorageOperation.created_at.desc())
            .limit(1)
            .with_for_update()
        )

    async def cleanup_candidates(self, deadline: datetime, limit: int, provider: str) -> list[UUID]:
        result = await self.session.scalars(
            select(StorageOperation.id)
            .where(
                StorageOperation.storage_provider == provider,
                or_(
                    (StorageOperation.kind == "DELETE")
                    & (StorageOperation.status == "CLEANUP_PENDING"),
                    (StorageOperation.kind == "UPLOAD")
                    & (StorageOperation.expires_at < deadline)
                    & (
                        (StorageOperation.temporary_key.is_not(None))
                        | StorageOperation.status.in_(
                            ["PENDING", "PROCESSING", "CANCELLED", "CLEANUP_PENDING"]
                        )
                    ),
                ),
            )
            .order_by(StorageOperation.updated_at, StorageOperation.id)
            .limit(limit)
        )
        return list(result)

    async def registered(self, provider: str, key: str) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        MediaAsset.storage_provider == provider, MediaAsset.storage_key == key
                    )
                )
            )
        )

    async def publicly_referenced(self, asset_id: UUID) -> bool:
        published = (
            Project.status == "PUBLISHED",
            Project.visibility.in_(["PUBLIC", "UNLISTED"]),
            Project.deleted_at.is_(None),
        )
        return bool(
            await self.session.scalar(
                select(
                    or_(
                        exists(
                            select(ProjectMedia.id)
                            .join(Project)
                            .where(ProjectMedia.media_id == asset_id, *published)
                        ),
                        exists(
                            select(ProjectSectionMedia.media_id)
                            .join(ProjectSection)
                            .join(Project)
                            .where(
                                ProjectSectionMedia.media_id == asset_id,
                                ProjectSection.is_visible.is_(True),
                                *published,
                            )
                        ),
                        exists().where(
                            Profile.is_active.is_(True),
                            or_(
                                Profile.profile_media_id == asset_id,
                                Profile.cv_media_id == asset_id,
                            ),
                        ),
                    )
                )
            )
        )
