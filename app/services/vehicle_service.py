import uuid
from typing import List, Optional

from fastapi import HTTPException, status

from app.models.audit import AuditAction
from app.repositories.audit_repository import AuditRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.search import VehicleSearchParams, PaginatedResponse
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from app.models.vehicle import Vehicle
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class VehicleService:
    def __init__(
        self,
        repository: VehicleRepository,
        audit_repository: Optional[AuditRepository] = None,
    ):
        self.repository = repository
        self.audit_repository = audit_repository

    async def create_vehicle(
        self,
        data: VehicleCreate,
        performed_by: Optional[uuid.UUID] = None,
    ) -> Vehicle:
        existing = await self.repository.get_by_vin(data.vin)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle with VIN {data.vin} already exists",
            )

        vehicle = await self.repository.create(data)

        logger.info(
            "vehicle_created",
            vehicle_id=str(vehicle.id),
            make=vehicle.make,
            model=vehicle.model,
            vin=vehicle.vin,
            performed_by=str(performed_by) if performed_by else None,
        )

        if self.audit_repository and performed_by:
            await self.audit_repository.create(
                action=AuditAction.VEHICLE_CREATED,
                performed_by=performed_by,
                entity_type="vehicle",
                entity_id=vehicle.id,
                details={
                    "make": vehicle.make,
                    "model": vehicle.model,
                    "vin": vehicle.vin,
                    "price": str(vehicle.price),
                    "quantity": vehicle.quantity,
                },
            )

        return vehicle

    async def get_vehicle(self, vehicle_id: uuid.UUID) -> Vehicle:
        vehicle = await self.repository.get_by_id(vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found",
            )
        return vehicle

    async def list_vehicles(
        self, skip: int = 0, limit: int = 20
    ) -> List[Vehicle]:
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_vehicle(
        self,
        vehicle_id: uuid.UUID,
        data: VehicleUpdate,
        performed_by: Optional[uuid.UUID] = None,
    ) -> Vehicle:
        vehicle = await self.get_vehicle(vehicle_id)

        # Capture the old values before update for the audit trail
        old_values = {
            "price": str(vehicle.price),
            "quantity": vehicle.quantity,
            "make": vehicle.make,
            "model": vehicle.model,
        }

        updated = await self.repository.update(vehicle, data)

        # Capture only the fields that actually changed
        new_values = data.model_dump(exclude_unset=True)
        changed_fields = {
            k: {"from": old_values.get(k), "to": str(v)}
            for k, v in new_values.items()
            if str(old_values.get(k)) != str(v)
        }

        logger.info(
            "vehicle_updated",
            vehicle_id=str(vehicle_id),
            changed_fields=list(changed_fields.keys()),
            performed_by=str(performed_by) if performed_by else None,
        )

        if self.audit_repository and performed_by and changed_fields:
            await self.audit_repository.create(
                action=AuditAction.VEHICLE_UPDATED,
                performed_by=performed_by,
                entity_type="vehicle",
                entity_id=vehicle_id,
                details={"changes": changed_fields},
            )

        return updated

    async def delete_vehicle(
        self,
        vehicle_id: uuid.UUID,
        performed_by: Optional[uuid.UUID] = None,
    ) -> dict:
        vehicle = await self.get_vehicle(vehicle_id)
        await self.repository.soft_delete(vehicle)

        logger.info(
            "vehicle_deleted",
            vehicle_id=str(vehicle_id),
            vin=vehicle.vin,
            performed_by=str(performed_by) if performed_by else None,
        )

        if self.audit_repository and performed_by:
            await self.audit_repository.create(
                action=AuditAction.VEHICLE_DELETED,
                performed_by=performed_by,
                entity_type="vehicle",
                entity_id=vehicle_id,
                details={"vin": vehicle.vin, "make": vehicle.make, "model": vehicle.model},
            )

        return {"message": "Vehicle deleted successfully"}

    async def search_vehicles(
        self, params: VehicleSearchParams
    ) -> PaginatedResponse:
        items, total = await self.repository.search(params)
        return PaginatedResponse.create(
            items=items,
            total=total,
            page=params.page,
            per_page=params.per_page,
        )