from fastapi import APIRouter, Depends, Response, status

from app.core.api_docs import error_responses
from app.modules.auth.dependencies import AuthServiceDependency, CurrentUser
from app.modules.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserResponse


def prevent_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


router = APIRouter(prefix="/auth", tags=["authentication"], dependencies=[Depends(prevent_caching)])


@router.post("/login", response_model=TokenResponse, responses=error_responses(401, 422, 429))
async def login(body: LoginRequest, service: AuthServiceDependency) -> TokenResponse:
    return await service.login(body.email, body.password.get_secret_value())


@router.post("/refresh", response_model=TokenResponse, responses=error_responses(401, 422, 429))
async def refresh(body: RefreshRequest, service: AuthServiceDependency) -> TokenResponse:
    return await service.refresh(body.refresh_token.get_secret_value())


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(422, 429))
async def logout(body: RefreshRequest, service: AuthServiceDependency) -> None:
    await service.logout(body.refresh_token.get_secret_value())


@router.get("/me", response_model=UserResponse, responses=error_responses(401))
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
