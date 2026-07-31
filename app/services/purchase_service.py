import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status

from app.models.audit import AuditAction
from app.models.user import UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.purchase_repository import PurchaseRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class PurchaseService:
    def __init__(
        self,
        vehicle_repository: VehicleRepository,
        purchase_repository: PurchaseRepository,
        audit_repository: Optional[AuditRepository] = None,
    ):
        self.vehicle_repo = vehicle_repository
        self.purchase_repo = purchase_repository
        self.audit_repo = audit_repository

    async def purchase_vehicle(
        self,
        vehicle_id: uuid.UUID,
        user_id: uuid.UUID,
        quantity: int,
        client_ip: Optional[str] = None,
    ):
        vehicle = await self.vehicle_repo.get_by_id_with_lock(vehicle_id)

        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found",
            )

        if vehicle.quantity < quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock. "
                    f"Available: {vehicle.quantity}, "
                    f"Requested: {quantity}"
                ),
            )

        vehicle.quantity -= quantity
        price_per_unit = vehicle.price
        total_amount = price_per_unit * Decimal(str(quantity))

        purchase = await self.purchase_repo.create(
            vehicle_id=vehicle_id,
            user_id=user_id,
            quantity=quantity,
            price_per_unit=price_per_unit,
            total_amount=total_amount,
        )

        logger.info(
            "vehicle_purchased",
            purchase_id=str(purchase.id),
            vehicle_id=str(vehicle_id),
            user_id=str(user_id),
            quantity=quantity,
            total_amount=str(total_amount),
        )

        if self.audit_repo:
            await self.audit_repo.create(
                action=AuditAction.VEHICLE_PURCHASED,
                performed_by=user_id,
                entity_type="purchase",
                entity_id=purchase.id,
                details={
                    "vehicle_id": str(vehicle_id),
                    "vehicle_make": vehicle.make,
                    "vehicle_model": vehicle.model,
                    "vehicle_vin": vehicle.vin,
                    "quantity": quantity,
                    "price_per_unit": str(price_per_unit),
                    "total_amount": str(total_amount),
                },
                client_ip=client_ip,
            )

        return purchase

    async def get_purchase(
        self,
        purchase_id: uuid.UUID,
        requesting_user_id: Optional[uuid.UUID] = None,
        is_admin: bool = False,
    ):
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
        purchases = await self.purchase_repo.get_by_user_id(
            user_id, skip=skip, limit=limit
        )
        total = await self.purchase_repo.count_by_user_id(user_id)
        return {
            "items": purchases,
            "total": total,
            "page": (skip // limit) + 1,
            "per_page": limit,
            "total_pages": -(-total // limit),
        }

    async def get_all_purchases(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        purchases = await self.purchase_repo.get_all(skip=skip, limit=limit)
        total = await self.purchase_repo.count_all()
        return {
            "items": purchases,
            "total": total,
            "page": (skip // limit) + 1,
            "per_page": limit,
            "total_pages": -(-total // limit),
        }