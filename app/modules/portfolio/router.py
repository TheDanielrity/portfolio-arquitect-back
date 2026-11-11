from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.core.api_docs import error_responses
from app.modules.auth.dependencies import get_current_user
from app.modules.portfolio.dependencies import Projects, Relations, Taxonomy
from app.modules.portfolio.schemas import (
    Assignment,
    AttributeCreate,
    AttributeResponse,
    AttributeUpdate,
    CategoryCreate,
    CategoryQuery,
    CategoryResponse,
    CategoryUpdate,
    CoverSelection,
    MediaAttach,
    MediaLinkResponse,
    MediaLinkUpdate,
    Page,
    PageQuery,
    ProjectCreate,
    ProjectQuery,
    ProjectResponse,
    ProjectUpdate,
    Reorder,
    TagCreate,
    TagQuery,
    TagResponse,
    TagUpdate,
)
from app.modules.portfolio.section_router import router as section_router
from app.modules.portfolio.taxonomy_service import TaxonPage, TaxonResponse


def prevent_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/admin",
    tags=["administrative portfolio"],
    dependencies=[Depends(get_current_user), Depends(prevent_caching)],
)
Pagination = Annotated[PageQuery, Query()]
router.include_router(section_router)


@router.get("/projects", response_model=Page[ProjectResponse], responses=error_responses(401, 422))
async def list_projects(
    query: Annotated[ProjectQuery, Query()], service: Projects
) -> Page[ProjectResponse]:
    return await service.list(query)


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=201,
    responses=error_responses(401, 409, 422),
)
async def create_project(body: ProjectCreate, service: Projects) -> ProjectResponse:
    return await service.create(body)


@router.put("/projects/order", status_code=204, responses=error_responses(401, 404, 422))
async def order_projects(body: Reorder, service: Projects) -> None:
    await service.reorder(body)


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    responses=error_responses(401, 404, 422),
)
async def get_project(project_id: UUID, service: Projects) -> ProjectResponse:
    return await service.get(project_id)


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    responses=error_responses(401, 404, 409, 422),
)
async def update_project(
    project_id: UUID, body: ProjectUpdate, service: Projects
) -> ProjectResponse:
    return await service.update(project_id, body)


@router.delete("/projects/{project_id}", status_code=204, responses=error_responses(401, 404, 422))
async def delete_project(project_id: UUID, service: Projects) -> None:
    await service.delete(project_id)


@router.get(
    "/categories", response_model=Page[CategoryResponse], responses=error_responses(401, 422)
)
async def list_categories(query: Annotated[CategoryQuery, Query()], service: Taxonomy) -> TaxonPage:
    return await service.list("categories", query)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=201,
    responses=error_responses(401, 409, 422),
)
async def create_category(body: CategoryCreate, service: Taxonomy) -> TaxonResponse:
    return await service.create(body)


@router.get(
    "/categories/{item_id}",
    response_model=CategoryResponse,
    responses=error_responses(401, 404, 422),
)
async def get_category(item_id: UUID, service: Taxonomy) -> TaxonResponse:
    return await service.get("categories", item_id)


@router.patch(
    "/categories/{item_id}",
    response_model=CategoryResponse,
    responses=error_responses(401, 404, 409, 422),
)
async def update_category(item_id: UUID, body: CategoryUpdate, service: Taxonomy) -> TaxonResponse:
    return await service.update("categories", item_id, body)


@router.delete(
    "/categories/{item_id}", status_code=204, responses=error_responses(401, 404, 409, 422)
)
async def delete_category(item_id: UUID, service: Taxonomy) -> None:
    await service.delete("categories", item_id)


@router.get("/tags", response_model=Page[TagResponse], responses=error_responses(401, 422))
async def list_tags(query: Annotated[TagQuery, Query()], service: Taxonomy) -> TaxonPage:
    return await service.list("tags", query)


@router.post(
    "/tags", response_model=TagResponse, status_code=201, responses=error_responses(401, 409, 422)
)
async def create_tag(body: TagCreate, service: Taxonomy) -> TaxonResponse:
    return await service.create(body)


@router.get("/tags/{item_id}", response_model=TagResponse, responses=error_responses(401, 404, 422))
async def get_tag(item_id: UUID, service: Taxonomy) -> TaxonResponse:
    return await service.get("tags", item_id)


@router.patch(
    "/tags/{item_id}", response_model=TagResponse, responses=error_responses(401, 404, 409, 422)
)
async def update_tag(item_id: UUID, body: TagUpdate, service: Taxonomy) -> TaxonResponse:
    return await service.update("tags", item_id, body)


@router.delete("/tags/{item_id}", status_code=204, responses=error_responses(401, 404, 409, 422))
async def delete_tag(item_id: UUID, service: Taxonomy) -> None:
    await service.delete("tags", item_id)


@router.get(
    "/projects/{project_id}/categories",
    response_model=Page[CategoryResponse],
    responses=error_responses(401, 404, 422),
)
async def project_categories(
    project_id: UUID, query: Annotated[CategoryQuery, Query()], service: Taxonomy
) -> TaxonPage:
    return await service.list("categories", query, project_id)


@router.put(
    "/projects/{project_id}/categories",
    status_code=204,
    responses=error_responses(401, 404, 409, 422),
)
async def assign_categories(project_id: UUID, body: Assignment, service: Taxonomy) -> None:
    await service.assign("categories", project_id, body)


@router.get(
    "/projects/{project_id}/tags",
    response_model=Page[TagResponse],
    responses=error_responses(401, 404, 422),
)
async def project_tags(
    project_id: UUID, query: Annotated[TagQuery, Query()], service: Taxonomy
) -> TaxonPage:
    return await service.list("tags", query, project_id)


@router.put(
    "/projects/{project_id}/tags", status_code=204, responses=error_responses(401, 404, 409, 422)
)
async def assign_tags(project_id: UUID, body: Assignment, service: Taxonomy) -> None:
    await service.assign("tags", project_id, body)


@router.get(
    "/projects/{project_id}/attributes",
    response_model=Page[AttributeResponse],
    responses=error_responses(401, 404, 422),
)
async def list_attributes(
    project_id: UUID, query: Pagination, service: Relations
) -> Page[AttributeResponse]:
    return await service.list_attributes(project_id, query)


@router.post(
    "/projects/{project_id}/attributes",
    response_model=AttributeResponse,
    status_code=201,
    responses=error_responses(401, 404, 409, 422),
)
async def add_attribute(
    project_id: UUID, body: AttributeCreate, service: Relations
) -> AttributeResponse:
    return await service.add_attribute(project_id, body)


@router.put(
    "/projects/{project_id}/attributes/order",
    status_code=204,
    responses=error_responses(401, 404, 422),
)
async def order_attributes(project_id: UUID, body: Reorder, service: Relations) -> None:
    await service.reorder("attributes", project_id, body)


@router.patch(
    "/projects/{project_id}/attributes/{item_id}",
    response_model=AttributeResponse,
    responses=error_responses(401, 404, 409, 422),
)
async def update_attribute(
    project_id: UUID, item_id: UUID, body: AttributeUpdate, service: Relations
) -> AttributeResponse:
    return await service.update_attribute(project_id, item_id, body)


@router.delete(
    "/projects/{project_id}/attributes/{item_id}",
    status_code=204,
    responses=error_responses(401, 404, 422),
)
async def delete_attribute(project_id: UUID, item_id: UUID, service: Relations) -> None:
    await service.delete_attribute(project_id, item_id)


@router.get(
    "/projects/{project_id}/media",
    response_model=Page[MediaLinkResponse],
    responses=error_responses(401, 404, 422),
)
async def list_media(
    project_id: UUID, query: Pagination, service: Relations
) -> Page[MediaLinkResponse]:
    return await service.list_media(project_id, query)


@router.post(
    "/projects/{project_id}/media",
    response_model=MediaLinkResponse,
    status_code=201,
    responses=error_responses(401, 404, 409, 422),
)
async def attach_media(
    project_id: UUID, body: MediaAttach, service: Relations
) -> MediaLinkResponse:
    return await service.attach(project_id, body)


@router.put(
    "/projects/{project_id}/media/order", status_code=204, responses=error_responses(401, 404, 422)
)
async def order_media(project_id: UUID, body: Reorder, service: Relations) -> None:
    await service.reorder("media", project_id, body)


@router.patch(
    "/projects/{project_id}/media/{item_id}",
    response_model=MediaLinkResponse,
    responses=error_responses(401, 404, 409, 422),
)
async def update_media(
    project_id: UUID, item_id: UUID, body: MediaLinkUpdate, service: Relations
) -> MediaLinkResponse:
    return await service.update_media(project_id, item_id, body)


@router.delete(
    "/projects/{project_id}/media/{item_id}",
    status_code=204,
    responses=error_responses(401, 404, 409, 422),
)
async def detach_media(project_id: UUID, item_id: UUID, service: Relations) -> None:
    await service.detach(project_id, item_id)


@router.put(
    "/projects/{project_id}/cover",
    response_model=MediaLinkResponse,
    responses=error_responses(401, 404, 409, 422),
)
async def select_cover(
    project_id: UUID, body: CoverSelection, service: Relations
) -> MediaLinkResponse:
    return await service.select_cover(project_id, body)
