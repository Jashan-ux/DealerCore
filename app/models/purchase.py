import uuid
from decimal import Decimal
from datetime import datetime

from sqlalchemy import Numeric, Integer, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PurchaseStatus(str):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Foreign keys link this record to the vehicle and the user.
    # ondelete="RESTRICT" means PostgreSQL will refuse to delete a vehicle
    # or user that has associated purchase records, protecting data integrity.
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    quantity_purchased: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Store the price at the time of purchase, not a reference to the
    # vehicle's current price. Vehicle prices change. A purchase record
    # must reflect what the customer actually paid, permanently.
    price_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=PurchaseStatus.COMPLETED,
        nullable=False
    )

    # Optional notes field for cancellation reasons or special circumstances
    notes: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships for convenient access in Python code.
    # lazy="selectin" means SQLAlchemy will load related objects automatically
    # using a separate SELECT IN query, which is safe and efficient in async.
    vehicle: Mapped["Vehicle"] = relationship(  # noqa: F821
        "Vehicle",
        lazy="selectin"
    )
    buyer: Mapped["User"] = relationship(  # noqa: F821
        "User",
        lazy="selectin"
    )