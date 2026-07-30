import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status

from app.models.user import UserRole
from app.repositories.purchase_repository import PurchaseRepository
from app.repositories.vehicle_repository import VehicleRepository


class PurchaseService:
    def __init__(
        self,
        vehicle_repository: VehicleRepository,
        purchase_repository: PurchaseRepository,
    ):
        self.vehicle_repo = vehicle_repository
        self.purchase_repo = purchase_repository

    async def purchase_vehicle(
        self,
        vehicle_id: uuid.UUID,
        user_id: uuid.UUID,
        quantity: int,
    ):
        """
        Execute a vehicle purchase with concurrency safety.

        The critical sequence is:
        1. Acquire a row-level lock on the vehicle with SELECT FOR UPDATE.
           No other transaction can modify this row until we commit.
        2. Read the quantity AFTER acquiring the lock, not before.
        3. Validate that sufficient stock exists.
        4. Decrement the quantity in the same transaction.
        5. Create the purchase audit record in the same transaction.
        6. Commit. The lock is released.

        Steps 1 through 6 happen within a single database transaction
        managed by the session dependency in the route layer.
        If any step raises an exception, the session dependency performs
        a rollback, undoing steps 4 and 5 automatically.
        """

        # Step 1 and 2: Lock the row and read the current quantity.
        # Using get_by_id_with_lock instead of get_by_id is the entire
        # difference between a correct and incorrect purchase endpoint.
        vehicle = await self.vehicle_repo.get_by_id_with_lock(vehicle_id)

        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found",
            )

        # Step 3: Validate stock AFTER acquiring the lock.
        # At this point we have an exclusive lock, so this quantity
        # reading is consistent and cannot be stale.
        if vehicle.quantity < quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock. "
                    f"Available: {vehicle.quantity}, "
                    f"Requested: {quantity}"
                ),
            )

        # Step 4: Decrement the quantity on the locked row.
        # This change is part of the current transaction and will be
        # committed atomically with the purchase record below.
        vehicle.quantity -= quantity

        # Step 5: Capture the price at this exact moment.
        # Prices may change later. The purchase record must reflect
        # what was actually charged, not what the price is in future.
        price_per_unit = vehicle.price
        total_amount = price_per_unit * Decimal(str(quantity))

        # Step 6: Create the purchase audit record.
        purchase = await self.purchase_repo.create(
            vehicle_id=vehicle_id,
            user_id=user_id,
            quantity=quantity,
            price_per_unit=price_per_unit,
            total_amount=total_amount,
        )

        return purchase

    async def get_purchase(
        self,
        purchase_id: uuid.UUID,
        requesting_user_id: Optional[uuid.UUID] = None,
        is_admin: bool = False,
    ):
        """
        Retrieve a single purchase by ID.

        If requesting_user_id is provided and is_admin is False,
        enforce that the requesting user owns this purchase.
        Admins can view any purchase.
        """
        purchase = await self.purchase_repo.get_by_id(purchase_id)

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase not found",
            )

        if not is_admin and requesting_user_id is not None:
            if purchase.user_id != requesting_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to view this purchase",
                )

        return purchase

    async def get_user_purchases(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        Get paginated purchase history for a specific user.
        The caller is responsible for ensuring the requesting user
        has permission to view this user's purchases.
        """
        purchases = await self.purchase_repo.get_by_user_id(
            user_id, skip=skip, limit=limit
        )
        total = await self.purchase_repo.count_by_user_id(user_id)

        return {
            "items": purchases,
            "total": total,
            "page": (skip // limit) + 1,
            "per_page": limit,
            "total_pages": -(-total // limit),  # ceiling division
        }

    async def get_all_purchases(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        Get paginated purchase history for all users.
        Admin-only operation.
        """
        purchases = await self.purchase_repo.get_all(skip=skip, limit=limit)
        total = await self.purchase_repo.count_all()

        return {
            "items": purchases,
            "total": total,
            "page": (skip // limit) + 1,
            "per_page": limit,
            "total_pages": -(-total // limit),
        }