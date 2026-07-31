import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import get_current_user, require_admin
from app.core.rate_limiter import limiter
from app.db.dependencies import get_db
from app.models.user import User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.purchase_repository import PurchaseRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.purchase import PurchaseCreate, PurchaseResponse
from app.services.purchase_service import PurchaseService

router = APIRouter(prefix="/purchases", tags=["Purchases"])


def get_purchase_service(db: AsyncSession = Depends(get_db)) -> PurchaseService:
    vehicle_repo = VehicleRepository(db)
    purchase_repo = PurchaseRepository(db)
    audit_repo = AuditRepository(db)
    return PurchaseService(vehicle_repo, purchase_repo, audit_repo)


@router.post(
    "",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Purchase a vehicle",
)
@limiter.limit("10/minute")
async def purchase_vehicle(
    request: Request,
    data: PurchaseCreate,
    current_user: User = Depends(get_current_user),
    service: PurchaseService = Depends(get_purchase_service),
):
    client_ip = request.client.host if request.client else None
    return await service.purchase_vehicle(
        vehicle_id=data.vehicle_id,
        user_id=current_user.id,
        quantity=data.quantity,
        client_ip=client_ip,
    )


@router.get(
    "/my",
    summary="Get the current user's purchase history",
)
async def get_my_purchases(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    service: PurchaseService = Depends(get_purchase_service),
):
    return await service.get_user_purchases(
        user_id=current_user.id, skip=skip, limit=limit
    )


@router.get(
    "",
    summary="Get all purchases — admin only",
)
async def get_all_purchases(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(require_admin),
    service: PurchaseService = Depends(get_purchase_service),
):
    return await service.get_all_purchases(skip=skip, limit=limit)


@router.get(
    "/{purchase_id}",
    response_model=PurchaseResponse,
    summary="Get a purchase by ID",
)
async def get_purchase(
    purchase_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: PurchaseService = Depends(get_purchase_service),
):
    is_admin = current_user.role == UserRole.ADMIN
    return await service.get_purchase(
        purchase_id=purchase_id,
        requesting_user_id=current_user.id,
        is_admin=is_admin,
    )