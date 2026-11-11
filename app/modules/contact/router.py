from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.core.api_docs import error_responses
from app.core.database import SessionDependency
from app.modules.auth.dependencies import get_current_user
from app.modules.contact.dependencies import SubmissionContext, get_submission_context
from app.modules.contact.schemas import (
    ContactCreate,
    ContactQuery,
    ContactReceipt,
    ContactResponse,
    ContactStatusUpdate,
)
from app.modules.contact.service import ContactService
from app.modules.portfolio.schemas import Page


def get_contact_service(session: SessionDependency) -> ContactService:
    return ContactService(session)


def prevent_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


Service = Annotated[ContactService, Depends(get_contact_service)]
public_router = APIRouter(
    prefix="/public/contact", tags=["contact"], dependencies=[Depends(prevent_caching)]
)
admin_router = APIRouter(
    prefix="/admin/contact-messages",
    tags=["administrative contact"],
    dependencies=[Depends(get_current_user), Depends(prevent_caching)],
)


@public_router.post(
    "", response_model=ContactReceipt, status_code=201, responses=error_responses(422, 429)
)
async def submit_contact(
    body: ContactCreate,
    service: Service,
    context: Annotated[SubmissionContext, Depends(get_submission_context)],
) -> ContactReceipt:
    return await service.submit(body, context)


@admin_router.get("", response_model=Page[ContactResponse], responses=error_responses(401, 422))
async def list_messages(
    query: Annotated[ContactQuery, Query()], service: Service
) -> Page[ContactResponse]:
    return await service.list(query)


@admin_router.get(
    "/{item_id}", response_model=ContactResponse, responses=error_responses(401, 404, 422)
)
async def get_message(item_id: UUID, service: Service) -> ContactResponse:
    return await service.get(item_id)


@admin_router.patch(
    "/{item_id}/status", response_model=ContactResponse, responses=error_responses(401, 404, 422)
)
async def set_status(item_id: UUID, body: ContactStatusUpdate, service: Service) -> ContactResponse:
    return await service.set_status(item_id, body)
