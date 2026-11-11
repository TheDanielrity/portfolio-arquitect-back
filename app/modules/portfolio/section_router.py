from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.api_docs import error_responses
from app.core.database import SessionDependency
from app.modules.portfolio.schemas import Page, PageQuery, Reorder
from app.modules.portfolio.section_schemas import (
    SectionCreate,
    SectionMediaInput,
    SectionMediaResponse,
    SectionMediaUpdate,
    SectionResponse,
    SectionUpdate,
)
from app.modules.portfolio.section_service import SectionService


def get_section_service(session: SessionDependency) -> SectionService:
    return SectionService(session)


Sections = Annotated[SectionService, Depends(get_section_service)]
Pagination = Annotated[PageQuery, Query()]
# Included by the authenticated portfolio router.
router = APIRouter(prefix="/projects/{project_id}/sections", tags=["project sections"])


@router.get("", response_model=Page[SectionResponse], responses=error_responses(401, 404, 422))
async def list_sections(
    project_id: UUID, query: Pagination, service: Sections
) -> Page[SectionResponse]:
    return await service.list(project_id, query)


@router.post(
    "",
    response_model=SectionResponse,
    status_code=201,
    responses=error_responses(401, 404, 409, 422),
)
async def create_section(
    project_id: UUID, body: SectionCreate, service: Sections
) -> SectionResponse:
    return await service.create(project_id, body)


@router.put("/order", status_code=204, responses=error_responses(401, 404, 422))
async def order_sections(project_id: UUID, body: Reorder, service: Sections) -> None:
    await service.reorder(project_id, body)


@router.get(
    "/{section_id}", response_model=SectionResponse, responses=error_responses(401, 404, 422)
)
async def get_section(project_id: UUID, section_id: UUID, service: Sections) -> SectionResponse:
    return await service.get(project_id, section_id)


@router.patch(
    "/{section_id}", response_model=SectionResponse, responses=error_responses(401, 404, 409, 422)
)
async def update_section(
    project_id: UUID, section_id: UUID, body: SectionUpdate, service: Sections
) -> SectionResponse:
    return await service.update(project_id, section_id, body)


@router.delete("/{section_id}", status_code=204, responses=error_responses(401, 404, 422))
async def delete_section(project_id: UUID, section_id: UUID, service: Sections) -> None:
    await service.delete(project_id, section_id)


@router.get(
    "/{section_id}/media",
    response_model=Page[SectionMediaResponse],
    responses=error_responses(401, 404, 422),
)
async def list_section_media(
    project_id: UUID, section_id: UUID, query: Pagination, service: Sections
) -> Page[SectionMediaResponse]:
    return await service.list_media(project_id, section_id, query)


@router.post(
    "/{section_id}/media",
    response_model=SectionMediaResponse,
    status_code=201,
    responses=error_responses(401, 404, 409, 422),
)
async def attach_section_media(
    project_id: UUID, section_id: UUID, body: SectionMediaInput, service: Sections
) -> SectionMediaResponse:
    return await service.attach(project_id, section_id, body)


@router.put("/{section_id}/media/order", status_code=204, responses=error_responses(401, 404, 422))
async def order_section_media(
    project_id: UUID, section_id: UUID, body: Reorder, service: Sections
) -> None:
    await service.reorder(project_id, body, section_id)


@router.patch(
    "/{section_id}/media/{media_id}",
    response_model=SectionMediaResponse,
    responses=error_responses(401, 404, 422),
)
async def update_section_media(
    project_id: UUID, section_id: UUID, media_id: UUID, body: SectionMediaUpdate, service: Sections
) -> SectionMediaResponse:
    return await service.update_media(project_id, section_id, media_id, body)


@router.delete(
    "/{section_id}/media/{media_id}", status_code=204, responses=error_responses(401, 404, 422)
)
async def detach_section_media(
    project_id: UUID, section_id: UUID, media_id: UUID, service: Sections
) -> None:
    await service.detach(project_id, section_id, media_id)
