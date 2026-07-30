import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, RefreshToken, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------ #
    # User operations
    # ------------------------------------------------------------------ #

    async def create(
        self,
        email: str,
        hashed_password: str,
        full_name: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        """
        Create a new user record.
        The caller is responsible for hashing the password before
        passing it here — the repository only deals with storage.
        """
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch a user by their UUID primary key."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Fetch a user by email address.
        Used during login to find the account before verifying the password.
        The email index on this column makes this lookup O(log n).
        """
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def update_role(self, user: User, new_role: UserRole) -> User:
        """Update a user's role. Only admins should call this via the service."""
        user.role = new_role
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def deactivate(self, user: User) -> User:
        """Soft-disable a user account without deleting the record."""
        user.is_active = False
        await self.session.flush()
        return user

    # ------------------------------------------------------------------ #
    # Refresh token operations
    # ------------------------------------------------------------------ #

    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """
        Store the hash of a refresh token in the database.
        We store the hash rather than the raw token for the same reason
        passwords are hashed: if this table is compromised, the attacker
        cannot use the hashes to authenticate.
        """
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(refresh_token)
        await self.session.flush()
        await self.session.refresh(refresh_token)
        return refresh_token

    async def get_refresh_token_by_hash(
        self, token_hash: str
    ) -> Optional[RefreshToken]:
        """
        Look up a refresh token record by its hash.
        This is called during the token refresh flow to verify
        the token exists, has not been revoked, and has not expired.
        """
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token_hash: str) -> None:
        """
        Mark a specific refresh token as revoked.
        Called during logout to invalidate the current session.
        The record is kept in the database rather than deleted
        for audit trail purposes.
        """
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()
        if token:
            token.is_revoked = True
            await self.session.flush()

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> None:
        """
        Revoke all refresh tokens for a user.
        Called when a user's password is changed or their account is
        compromised, forcing them to log in again on all devices.
        """
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
            )
        )
        tokens = result.scalars().all()
        for token in tokens:
            token.is_revoked = True
        await self.session.flush()

    async def delete_expired_tokens(self) -> int:
        """
        Delete all expired refresh token records from the database.
        This is a maintenance operation that should be called periodically
        (e.g., via a scheduled job) to prevent the refresh_tokens table
        from growing unboundedly.
        Returns the number of deleted records.
        """
        result = await self.session.execute(
            delete(RefreshToken)
            .where(RefreshToken.expires_at < datetime.utcnow())
            .returning(RefreshToken.id)
        )
        deleted = result.fetchall()
        await self.session.flush()
        return len(deleted)