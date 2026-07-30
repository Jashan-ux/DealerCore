from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import uuid
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from sqlalchemy import select, func, asc, desc
from app.schemas.search import VehicleSearchParams, ALLOWED_SORT_COLUMNS

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

    

    async def search(
        self,
        params: VehicleSearchParams,
    ) -> tuple[list[Vehicle], int]:
        """
        Build and execute a dynamic search query based on the provided params.

        The query is built incrementally: start with the base query and
        add WHERE clauses only for parameters that were actually provided.
        This avoids filtering on NULL values which would return no results.

        The count query uses a subquery so that both the total count and
        the paginated results derive from the same filter logic, ensuring
        consistency between the two numbers.
        """

        # Start with the base query, always excluding soft-deleted records
        base_query = select(Vehicle).where(Vehicle.is_deleted == False)

        # ---------------------------------------------------------------- #
        # Apply filters conditionally
        # ---------------------------------------------------------------- #

        if params.make is not None:
            # ilike is case-insensitive LIKE in SQLAlchemy
            # The % wildcards on both sides allow partial matching
            base_query = base_query.where(
                Vehicle.make.ilike(f"%{params.make}%")
            )

        if params.model is not None:
            base_query = base_query.where(
                Vehicle.model.ilike(f"%{params.model}%")
            )

        if params.year_min is not None:
            base_query = base_query.where(Vehicle.year >= params.year_min)

        if params.year_max is not None:
            base_query = base_query.where(Vehicle.year <= params.year_max)

        if params.category is not None:
            base_query = base_query.where(Vehicle.category == params.category)

        if params.price_min is not None:
            base_query = base_query.where(Vehicle.price >= params.price_min)

        if params.price_max is not None:
            base_query = base_query.where(Vehicle.price <= params.price_max)

        if params.color is not None:
            base_query = base_query.where(
                Vehicle.color.ilike(f"%{params.color}%")
            )

        if params.in_stock is True:
            base_query = base_query.where(Vehicle.quantity > 0)

        # ---------------------------------------------------------------- #
        # Count total matching results BEFORE applying sort and pagination.
        # We wrap base_query as a subquery so the count uses identical filters.
        # ---------------------------------------------------------------- #

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # ---------------------------------------------------------------- #
        # Apply sorting
        # ---------------------------------------------------------------- #

        # getattr safely maps the string column name to the actual
        # SQLAlchemy column object. We fall back to created_at if somehow
        # an invalid column slips through (belt-and-suspenders safety).
        sort_column = getattr(Vehicle, params.sort_by, Vehicle.created_at)

        if params.sort_order == "desc":
            base_query = base_query.order_by(desc(sort_column))
        else:
            base_query = base_query.order_by(asc(sort_column))

        # ---------------------------------------------------------------- #
        # Apply pagination AFTER sorting
        # ---------------------------------------------------------------- #

        paginated_query = base_query.offset(params.offset).limit(params.per_page)

        result = await self.session.execute(paginated_query)
        items = list(result.scalars().all())

        return items, total