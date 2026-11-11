from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.database import SessionDependency
from app.core.exceptions import AuthenticationError
from app.core.security import Security
from app.models import AppUser
from app.modules.auth.service import AuthService

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description="Access token from JSON login/refresh. Rotation invalidates the previous token.",
)


def get_auth_service(request: Request, session: SessionDependency) -> AuthService:
    return AuthService(
        session,
        cast(Security, request.app.state.security),
        cast(Settings, request.app.state.settings),
    )


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    service: AuthServiceDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AppUser:
    if credentials is None:
        raise AuthenticationError
    return await service.authenticate(credentials.credentials)


CurrentUser = Annotated[AppUser, Depends(get_current_user)]
