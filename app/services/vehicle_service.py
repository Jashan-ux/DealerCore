from fastapi import HTTPException, status
from typing import List
import uuid
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from app.models.vehicle import Vehicle

class VehicleService:
    def __init__(self, repository: VehicleRepository):
        self.repository = repository

    async def create_vehicle(self, data: VehicleCreate) -> Vehicle:
        existing = await self.repository.get_by_vin(data.vin)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle with VIN {data.vin} already exists"
            )
        return await self.repository.create(data)

    async def get_vehicle(self, vehicle_id: uuid.UUID) -> Vehicle:
        vehicle = await self.repository.get_by_id(vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        return vehicle

    async def list_vehicles(self, skip: int = 0, limit: int = 20) -> List[Vehicle]:
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_vehicle(self, vehicle_id: uuid.UUID, data: VehicleUpdate) -> Vehicle:
        vehicle = await self.get_vehicle(vehicle_id)
        return await self.repository.update(vehicle, data)

    async def delete_vehicle(self, vehicle_id: uuid.UUID) -> dict:
        vehicle = await self.get_vehicle(vehicle_id)
        await self.repository.soft_delete(vehicle)
        return {"message": "Vehicle deleted successfully"}