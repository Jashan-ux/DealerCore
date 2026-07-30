from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import uuid
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate


class VehicleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: VehicleCreate) -> Vehicle:
        vehicle = Vehicle(**data.model_dump())
        self.session.add(vehicle)
        await self.session.flush()  # flush sends SQL but does not commit
        await self.session.refresh(vehicle)  # reload from DB to get defaults
        return vehicle

    async def get_by_id(self, vehicle_id: uuid.UUID) -> Optional[Vehicle]:
        result = await self.session.execute(
            select(Vehicle).where(
                Vehicle.id == vehicle_id,
                Vehicle.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 20) -> List[Vehicle]:
        result = await self.session.execute(
            select(Vehicle)
            .where(Vehicle.is_deleted == False)
            .offset(skip)
            .limit(limit)
            .order_by(Vehicle.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, vehicle: Vehicle, data: VehicleUpdate) -> Vehicle:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(vehicle, field, value)
        await self.session.flush()
        await self.session.refresh(vehicle)
        return vehicle

    async def soft_delete(self, vehicle: Vehicle) -> Vehicle:
        vehicle.is_deleted = True
        await self.session.flush()
        return vehicle

    async def get_by_vin(self, vin: str) -> Optional[Vehicle]:
        result = await self.session.execute(
            select(Vehicle).where(Vehicle.vin == vin)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_lock(self, vehicle_id: uuid.UUID) -> Optional[Vehicle]:
        """
        Fetch a vehicle and acquire a PostgreSQL row-level lock using
        SELECT FOR UPDATE.

        Any other transaction that calls this method on the same row will
        block and wait until this transaction either commits or rolls back.
        This is the mechanism that prevents overselling.

        Only call this method within an active transaction where you intend
        to modify the row immediately afterward.
        """
        result = await self.session.execute(
            select(Vehicle)
            .where(
                Vehicle.id == vehicle_id,
                Vehicle.is_deleted == False,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()