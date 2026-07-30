import uuid
from datetime import datetime

from fastapi import HTTPException, status

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_token,
    decode_token,
)
from app.models.user import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRegister, UserResponse


class AuthService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def register(self, data: UserRegister) -> UserResponse:
        """
        Register a new user account.
        Check for email uniqueness first, then hash the password,
        then persist. The raw password never touches the database.
        """
        existing = await self.repository.get_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        hashed = hash_password(data.password)
        user = await self.repository.create(
            email=data.email,
            hashed_password=hashed,
            full_name=data.full_name,
            role=UserRole.USER,
        )
        return user

    async def login(self, email: str, password: str) -> dict:
        """
        Authenticate a user and return access + refresh tokens.

        The error message for wrong password is deliberately the same as
        for user not found. Distinguishing between the two would tell an
        attacker which emails are registered in your system (user enumeration).
        """
        user = await self.repository.get_by_email(email)

        # Check existence and password in a way that gives the same error
        # message regardless of which check failed
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled. Contact support.",
            )

        # Create the access token (stateless, not stored)
        access_token = create_access_token(
            user_id=str(user.id),
            role=user.role.value,
        )

        # Create the refresh token and store its hash
        refresh_token, expires_at = create_refresh_token(user_id=str(user.id))
        token_hash = hash_token(refresh_token)

        await self.repository.create_refresh_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Exchange a valid refresh token for a new access token.
        Validates the JWT signature, then checks the database record
        to ensure it has not been revoked.
        """
        # First verify the JWT signature and decode the payload
        try:
            payload = decode_token(refresh_token)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        # Check the database record for revocation
        token_hash = hash_token(refresh_token)
        token_record = await self.repository.get_refresh_token_by_hash(token_hash)

        if not token_record or token_record.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        if token_record.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )

        # Fetch the user to get their current role
        # (role may have changed since the refresh token was issued)
        user_id = uuid.UUID(payload["sub"])
        user = await self.repository.get_by_id(user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        new_access_token = create_access_token(
            user_id=str(user.id),
            role=user.role.value,
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
        }

    async def logout(self, refresh_token: str) -> dict:
        """
        Revoke the refresh token to invalidate the session.
        The access token will expire naturally after 15 minutes.
        """
        token_hash = hash_token(refresh_token)
        await self.repository.revoke_refresh_token(token_hash)
        return {"message": "Successfully logged out"}

    async def change_user_role(
        self,
        target_user_id: uuid.UUID,
        new_role: UserRole,
    ) -> UserResponse:
        """
        Change a user's role. Only callable by admin users.
        The role check is enforced in the route layer via the
        require_admin dependency, not here.
        """
        user = await self.repository.get_by_id(target_user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        updated = await self.repository.update_role(user, new_role)
        return updated