import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.purchase import Purchase, PurchaseStatus
from app.models.vehicle import Vehicle


class PurchaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        vehicle_id: uuid.UUID,
        user_id: uuid.UUID,
        quantity: int,
        price_per_unit: Decimal,
        total_amount: Decimal,
        notes: Optional[str] = None,
    ) -> Purchase:
        """
        Create a new purchase record.
        This is called only after the vehicle quantity has already been
        decremented within the same transaction in the service layer.
        """
        purchase = Purchase(
            vehicle_id=vehicle_id,
            user_id=user_id,
            quantity_purchased=quantity,
            price_per_unit=price_per_unit,
            total_amount=total_amount,
            status=PurchaseStatus.COMPLETED,
            notes=notes,
        )
        self.session.add(purchase)
        await self.session.flush()
        await self.session.refresh(purchase)
        return purchase

    async def get_by_id(
        self, purchase_id: uuid.UUID
    ) -> Optional[Purchase]:
        """
        Fetch a purchase by ID with vehicle and buyer details loaded.
        The selectinload option eagerly loads the relationships defined
        on the Purchase model, avoiding lazy-load issues in async context.
        """
        result = await self.session.execute(
            select(Purchase)
            .options(
                selectinload(Purchase.vehicle),
                selectinload(Purchase.buyer),
            )
            .where(Purchase.id == purchase_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Purchase]:
        """
        Fetch all purchases made by a specific user, newest first.
        Regular users call this to see their own purchase history.
        """
        result = await self.session.execute(
            select(Purchase)
            .options(selectinload(Purchase.vehicle))
            .where(Purchase.user_id == user_id)
            .order_by(Purchase.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Purchase]:
        """
        Fetch all purchases across all users, newest first.
        Admin-only operation for inventory oversight.
        """
        result = await self.session.execute(
            select(Purchase)
            .options(
                selectinload(Purchase.vehicle),
                selectinload(Purchase.buyer),
            )
            .order_by(Purchase.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_vehicle_id(
        self,
        vehicle_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Purchase]:
        """
        Fetch all purchases of a specific vehicle.
        Useful for admins to see which users bought a particular model.
        """
        result = await self.session.execute(
            select(Purchase)
            .options(selectinload(Purchase.buyer))
            .where(Purchase.vehicle_id == vehicle_id)
            .order_by(Purchase.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_user_id(self, user_id: uuid.UUID) -> int:
        """Count total purchases by a user for pagination metadata."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count(Purchase.id))
            .where(Purchase.user_id == user_id)
        )
        return result.scalar_one()

    async def count_all(self) -> int:
        """Count total purchases for pagination metadata."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count(Purchase.id))
        )
        return result.scalar_one()