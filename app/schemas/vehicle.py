from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional
from decimal import Decimal
from datetime import datetime
import uuid
from app.models.vehicle import VehicleCategory

class VehicleBase(BaseModel):
    make: str
    model: str
    year: int
    vin: str
    category: VehicleCategory
    price: Decimal
    quantity: int
    color: Optional[str] = None
    description: Optional[str] = None

    @field_validator("year")
    @classmethod
    def year_must_be_valid(cls, v):
        if v < 1886 or v > datetime.now().year + 1:
            raise ValueError("Year must be between 1886 and next year")
        return v

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Price must be positive")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError("Quantity cannot be negative")
        return v

    @field_validator("vin")
    @classmethod
    def vin_must_be_valid_length(cls, v):
        if len(v) != 17:
            raise ValueError("VIN must be exactly 17 characters")
        return v.upper()

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    category: Optional[VehicleCategory] = None
    price: Optional[Decimal] = None
    quantity: Optional[int] = None
    color: Optional[str] = None
    description: Optional[str] = None

class VehicleResponse(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_deleted: bool
    created_at: datetime
    updated_at: datetime