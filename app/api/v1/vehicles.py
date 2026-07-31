from fastapi import APIRouter, Depends, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from decimal import Decimal
import uuid

from app.core.auth_dependencies import get_current_user, require_admin
from app.core.rate_limiter import limiter
from app.db.dependencies import get_db
from app.models.user import User
from app.models.vehicle import VehicleCategory
from app.repositories.audit_repository import AuditRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.search import VehicleSearchParams, PaginatedResponse
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from app.services.vehicle_service import VehicleService

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


def get_vehicle_service(db: AsyncSession = Depends(get_db)) -> VehicleService:
    repo = VehicleRepository(db)
    audit_repo = AuditRepository(db)
    return VehicleService(repo, audit_repo)


@router.post(
    "",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new vehicle to inventory",
    description="Admin only. Creates a new vehicle record. VIN must be unique.",
)
async def create_vehicle(
    data: VehicleCreate,
    service: VehicleService = Depends(get_vehicle_service),
    current_user: User = Depends(require_admin),
):
    return await service.create_vehicle(data, performed_by=current_user.id)


@router.get(
    "/search",
    response_model=PaginatedResponse[VehicleResponse],
    summary="Search and filter vehicles",
)
@limiter.limit("30/minute")
async def search_vehicles(
    request: Request,   # required by slowapi for rate limiting
    make: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    year_min: Optional[int] = Query(default=None, ge=1886),
    year_max: Optional[int] = Query(default=None, le=2030),
    category: Optional[VehicleCategory] = Query(default=None),
    price_min: Optional[Decimal] = Query(default=None, ge=0),
    price_max: Optional[Decimal] = Query(default=None, ge=0),
    color: Optional[str] = Query(default=None),
    in_stock: Optional[bool] = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    service: VehicleService = Depends(get_vehicle_service),
    current_user: User = Depends(get_current_user),
):
    try:
        params = VehicleSearchParams(
            make=make, model=model, year_min=year_min, year_max=year_max,
            category=category, price_min=price_min, price_max=price_max,
            color=color, in_stock=in_stock, sort_by=sort_by,
            sort_order=sort_order, page=page, per_page=per_page,
        )
    except ValidationError as e:
        raise RequestValidationError(e.errors())
    return await service.search_vehicles(params)


@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Get a vehicle by ID",
)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    service: VehicleService = Depends(get_vehicle_service),
    current_user: User = Depends(get_current_user),
):
    return await service.get_vehicle(vehicle_id)


@router.get(
    "",
    response_model=List[VehicleResponse],
    summary="List all vehicles with pagination",
)
async def list_vehicles(
    skip: int = 0,
    limit: int = 20,
    service: VehicleService = Depends(get_vehicle_service),
    current_user: User = Depends(get_current_user),
):
    return await service.list_vehicles(skip=skip, limit=limit)


@router.patch(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Update vehicle details — admin only",
)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    data: VehicleUpdate,
    service: VehicleService = Depends(get_vehicle_service),
    current_user: User = Depends(require_admin),
):
    return await service.update_vehicle(
        vehicle_id, data, performed_by=current_user.id
    )


@router.delete(
    "/{vehicle_id}",
    summary="Soft delete a vehicle — admin only",
)
async def delete_vehicle(
    vehicle_id: uuid.UUID,
    service: VehicleService = Depends(get_vehicle_service),
    current_user: User = Depends(require_admin),
):
    return await service.delete_vehicle(
        vehicle_id, performed_by=current_user.id
    )