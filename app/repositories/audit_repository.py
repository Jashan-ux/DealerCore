import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog, AuditAction


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        action: AuditAction,
        entity_type: str,
        entity_id: Optional[uuid.UUID] = None,
        performed_by: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        client_ip: Optional[str] = None,
    ) -> AuditLog:
        """
        Create an immutable audit log entry.

        This method should be called within the same database transaction
        as the action being audited. That way, if the action rolls back,
        the audit log entry rolls back with it, keeping the two in sync.
        """
        log = AuditLog(
            action=action.value,
            performed_by=performed_by,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            client_ip=client_ip,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_by_entity(
        self,
        entity_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AuditLog]:
        """
        Get all audit log entries for a specific entity, newest first.
        Useful for showing the change history of a vehicle or purchase.
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AuditLog]:
        """
        Get all audit log entries for actions performed by a specific user.
        Useful for admin investigation of user activity.
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.performed_by == user_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_action(
        self,
        action: AuditAction,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AuditLog]:
        """
        Get all audit log entries for a specific action type.
        Useful for seeing all purchases, all deletions, etc.
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.action == action.value)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AuditLog]:
        """
        Get all audit log entries, newest first.
        Admin-only operation.
        """
        result = await self.session.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())