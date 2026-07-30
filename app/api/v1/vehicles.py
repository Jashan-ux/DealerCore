from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.core.auth_dependencies import get_current_user, require_admin
from app.db.dependencies import get_db
from app.models.user import User
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from app.services.vehicle_service import VehicleService

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