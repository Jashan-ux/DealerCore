from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    AccessTokenResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
    UserRoleUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(tags=["Authentication"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    repo = UserRepository(db)
    return AuthService(repo)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description=(
        "Creates a new user with the USER role. "
        "Email must be unique. Password must be at least 8 characters, "
        "contain one uppercase letter and one digit."
    ),
)
async def register(
    data: UserRegister,
    service: AuthService = Depends(get_auth_service),
):
    return await service.register(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and obtain access and refresh tokens",
    description=(
        "Accepts form-encoded credentials (username = email, password). "
        "Returns a short-lived access token (15 min) and a "
        "long-lived refresh token (7 days)."
    ),
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
):
    # OAuth2PasswordRequestForm uses 'username' field for the email
    result = await service.login(form_data.username, form_data.password)
    return result


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Exchange refresh token for a new access token",
)
async def refresh_token(
    data: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.refresh_access_token(data.refresh_token)


@router.post(
    "/logout",
    summary="Logout and revoke the refresh token",
    description="Revokes the provided refresh token. The access token expires naturally.",
)
async def logout(
    data: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    return await service.logout(data.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user's profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user