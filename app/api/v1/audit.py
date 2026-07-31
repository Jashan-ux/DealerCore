import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import require_admin
from app.db.dependencies import get_db
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.audit_repository import AuditRepository

router = APIRouter(prefix="/audit", tags=["Audit"])


def get_audit_repo(db: AsyncSession = Depends(get_db)) -> AuditRepository:
    return AuditRepository(db)


@router.get(
    "",
    summary="Get all audit logs — admin only",
    description="Returns the complete audit trail. Admin access required.",
)
async def get_all_audit_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    repo: AuditRepository = Depends(get_audit_repo),
):
    return await repo.get_all(skip=skip, limit=limit)


@router.get(
    "/entity/{entity_id}",
    summary="Get audit logs for a specific entity — admin only",
    description="Returns the change history for a specific vehicle, purchase, or user.",
)
async def get_audit_logs_by_entity(
    entity_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    repo: AuditRepository = Depends(get_audit_repo),
):
    return await repo.get_by_entity(entity_id, skip=skip, limit=limit)


@router.get(
    "/user/{user_id}",
    summary="Get audit logs for actions performed by a user — admin only",
)
async def get_audit_logs_by_user(
    user_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    repo: AuditRepository = Depends(get_audit_repo),
):
    return await repo.get_by_user(user_id, skip=skip, limit=limit)