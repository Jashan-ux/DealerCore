import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.dependencies import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

# This tells FastAPI where clients can obtain a token.
# It also makes the lock icon appear in Swagger docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the JWT access token and return the current authenticated user.
    This dependency is injected into any route that requires authentication.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except ValueError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise credentials_exception

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    return user


def require_role(*roles: UserRole):
    """
    Factory function that returns a dependency requiring the current user
    to have one of the specified roles.

    Usage:
        require_admin = require_role(UserRole.ADMIN)
        require_admin_or_manager = require_role(UserRole.ADMIN, UserRole.MANAGER)

    The factory pattern is used instead of a fixed dependency because
    different endpoints need different role requirements.
    """
    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {[r.value for r in roles]}",
            )
        return current_user
    return role_checker


# Pre-built role dependencies for convenience
require_admin = require_role(UserRole.ADMIN)
require_admin_or_manager = require_role(UserRole.ADMIN, UserRole.MANAGER)
