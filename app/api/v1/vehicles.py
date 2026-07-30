from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from pydantic import ValidationError

from app.core.auth_dependencies import get_current_user, require_admin
from app.db.dependencies import get_db
from app.models.user import User
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from app.services.vehicle_service import VehicleService
from fastapi import Query
from app.schemas.search import VehicleSearchParams, PaginatedResponse
from app.models.vehicle import VehicleCategory
from decimal import Decimal
from typing import Optional
router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


def get_vehicle_service(db: AsyncSession = Depends(get_db)) -> VehicleService:
    repo = VehicleRepository(db)
    return VehicleService(repo)


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
):
    return await service.create_vehicle(data)



@router.get(
    "/search",
    summary="Search and filter vehicles",
    description=(
        "Search vehicles with optional filters for make, model, year range, "
        "category, price range, color, and stock status. "
        "Results are sortable and paginated. "
        "All string filters are case-insensitive partial matches."
    ),
)
async def search_vehicles(
    # Filter params — FastAPI reads these from query string automatically
    make: Optional[str] = Query(default=None, description="Partial match on make name"),
    model: Optional[str] = Query(default=None, description="Partial match on model name"),
    year_min: Optional[int] = Query(default=None, ge=1886, description="Minimum year"),
    year_max: Optional[int] = Query(default=None, le=2030, description="Maximum year"),
    category: Optional[VehicleCategory] = Query(default=None),
    price_min: Optional[Decimal] = Query(default=None, ge=0),
    price_max: Optional[Decimal] = Query(default=None, ge=0),
    color: Optional[str] = Query(default=None),
    in_stock: Optional[bool] = Query(default=None, description="If true, only return vehicles with quantity > 0"),

    # Sort params
    sort_by: str = Query(default="created_at", description="Field to sort by"),
    sort_order: str = Query(default="desc", description="Sort direction: asc or desc"),

    # Pagination params
    page: int = Query(default=1, ge=1, description="Page number, 1-indexed"),
    per_page: int = Query(default=20, ge=1, le=100, description="Results per page"),

    # Dependencies
    service: VehicleService = Depends(get_vehicle_service),
    current_user: User = Depends(get_current_user),
):
    # Assemble the search params model from individual query params.
    # This triggers Pydantic validation including cross-field validators.
    try:
        params = VehicleSearchParams(
            make=make,
            model=model,
            year_min=year_min,
            year_max=year_max,
            category=category,
            price_min=price_min,
            price_max=price_max,
            color=color,
            in_stock=in_stock,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            per_page=per_page,
        )
    except ValidationError as exc:
        normalized_errors = []
        for error in exc.errors():
            normalized_error = dict(error)
            if "ctx" in normalized_error and normalized_error["ctx"]:
                normalized_error["ctx"] = {
                    key: jsonable_encoder(value) if not isinstance(value, (str, int, float, bool)) else value
                    for key, value in normalized_error["ctx"].items()
                }
            if "input" in normalized_error and normalized_error["input"] is not None:
                normalized_error["input"] = jsonable_encoder(normalized_error["input"])
            normalized_errors.append(normalized_error)

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=normalized_errors,
        ) from exc

    return await service.search_vehicles(params)



@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Get a vehicle by ID",
)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    service: VehicleService = Depends(get_vehicle_service),
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
):
    return await service.list_vehicles(skip=skip, limit=limit)


@router.patch(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Update vehicle details",
)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    data: VehicleUpdate,
    service: VehicleService = Depends(get_vehicle_service),
):
    return await service.update_vehicle(vehicle_id, data)


@router.delete(
    "/{vehicle_id}",
    summary="Soft delete a vehicle — admin only",
)
async def delete_vehicle(
    vehicle_id: uuid.UUID,
    service: VehicleService = Depends(get_vehicle_service),
    current_user: User = Depends(require_admin),
):
    return await service.delete_vehicle(vehicle_id)