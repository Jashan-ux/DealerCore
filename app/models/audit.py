import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditAction(str, enum.Enum):
    """
    Enumeration of every auditable action in the system.
    Adding a new action here is the first step whenever a new
    significant operation is added to the application.
    """
    # Vehicle actions
    VEHICLE_CREATED = "vehicle_created"
    VEHICLE_UPDATED = "vehicle_updated"
    VEHICLE_DELETED = "vehicle_deleted"
    VEHICLE_RESTOCKED = "vehicle_restocked"

    # Purchase actions
    VEHICLE_PURCHASED = "vehicle_purchased"
    PURCHASE_CANCELLED = "purchase_cancelled"
    PURCHASE_REFUNDED = "purchase_refunded"

    # User actions
    USER_REGISTERED = "user_registered"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_DEACTIVATED = "user_deactivated"

    # Auth actions
    USER_LOGGED_IN = "user_logged_in"
    USER_LOGGED_OUT = "user_logged_out"
    PASSWORD_CHANGED = "password_changed"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # The action that was performed
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )

    # The user who performed the action.
    # Nullable because some actions (failed login attempts) may not
    # have an authenticated user associated with them.
    performed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True
    )

    # The type of entity affected (vehicle, user, purchase)
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )

    # The ID of the specific entity affected
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True
    )

    # JSONB stores arbitrary structured data efficiently in PostgreSQL.
    # This holds the relevant state changes or context for the action,
    # for example the old and new price when a vehicle is updated.
    # JSONB is binary-encoded and supports indexing, unlike plain JSON.
    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict
    )

    # The IP address of the client who made the request.
    # Useful for security investigations.
    client_ip: Mapped[str] = mapped_column(
        String(45),  # 45 chars accommodates IPv6 addresses
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )