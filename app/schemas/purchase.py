import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator, ConfigDict

from app.schemas.vehicle import VehicleResponse
from app.schemas.user import UserResponse


class PurchaseCreate(BaseModel):
    """
    What the client sends when initiating a purchase.
    Deliberately minimal — the server determines price and total.
    """
    vehicle_id: uuid.UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be at least 1")
        return v


class PurchaseResponse(BaseModel):
    """
    What the server returns after a purchase.
    Includes denormalized vehicle and buyer info for convenience.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    user_id: uuid.UUID
    quantity_purchased: int
    price_per_unit: Decimal
    total_amount: Decimal
    status: str
    notes: Optional[str]
    created_at: datetime

    # Nested objects — populated by SQLAlchemy's selectin loading
    vehicle: Optional[VehicleResponse] = None
    buyer: Optional[UserResponse] = None


class PurchaseListResponse(BaseModel):
    """Paginated list of purchases."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    user_id: uuid.UUID
    quantity_purchased: int
    price_per_unit: Decimal
    total_amount: Decimal
    status: str
    created_at: datetime