from decimal import Decimal
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, field_validator, model_validator

from app.models.vehicle import VehicleCategory

# Generic type variable used to make PaginatedResponse reusable
# across vehicles, purchases, and any future list endpoint.
T = TypeVar("T")


# Allowed sort columns as a set for O(1) lookup during validation.
# Using a set instead of a list prevents a linear scan on every request.
ALLOWED_SORT_COLUMNS = {"price", "year", "make", "model", "created_at"}


class VehicleSearchParams(BaseModel):
    """
    Pydantic model for all vehicle search query parameters.

    Using a Pydantic model for query parameters rather than individual
    function arguments gives you automatic validation, clear documentation
    in Swagger, and a single object you can pass through your layers.
    """

    # Filter fields — all optional, only applied when provided
    make: Optional[str] = None
    model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    category: Optional[VehicleCategory] = None
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    color: Optional[str] = None
    in_stock: Optional[bool] = None

    # Sort fields
    sort_by: str = "created_at"
    sort_order: str = "desc"

    # Pagination fields
    page: int = 1
    per_page: int = 20

    @field_validator("sort_by")
    @classmethod
    def sort_by_must_be_valid_column(cls, v: str) -> str:
        if v not in ALLOWED_SORT_COLUMNS:
            raise ValueError(
                f"sort_by must be one of: {sorted(ALLOWED_SORT_COLUMNS)}"
            )
        return v

    @field_validator("sort_order")
    @classmethod
    def sort_order_must_be_valid(cls, v: str) -> str:
        if v not in {"asc", "desc"}:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        return v.lower()

    @field_validator("page")
    @classmethod
    def page_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("page must be 1 or greater")
        return v

    @field_validator("per_page")
    @classmethod
    def per_page_must_be_in_range(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("per_page must be between 1 and 100")
        return v

    @model_validator(mode="after")
    def year_range_must_be_valid(self) -> "VehicleSearchParams":
        """
        Cross-field validation: year_min cannot exceed year_max.
        This is a model_validator rather than a field_validator because
        it needs to see both fields simultaneously after they are parsed.
        """
        if self.year_min is not None and self.year_max is not None:
            if self.year_min > self.year_max:
                raise ValueError("year_min cannot be greater than year_max")
        return self

    @model_validator(mode="after")
    def price_range_must_be_valid(self) -> "VehicleSearchParams":
        """Cross-field validation: price_min cannot exceed price_max."""
        if self.price_min is not None and self.price_max is not None:
            if self.price_min > self.price_max:
                raise ValueError("price_min cannot be greater than price_max")
        return self

    @property
    def offset(self) -> int:
        """Calculate the SQL OFFSET value from page and per_page."""
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """
    A generic paginated response wrapper.
    Generic[T] means this same schema works for vehicles, purchases,
    or any other list response. PaginatedResponse[VehicleResponse]
    produces a response with items typed as List[VehicleResponse].
    """
    items: List[T]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        per_page: int,
    ) -> "PaginatedResponse[T]":
        """
        Factory method that calculates derived pagination fields
        so callers do not need to compute them manually.
        Ceiling division without importing math: -(-a // b)
        """
        total_pages = -(-total // per_page) if total > 0 else 1
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )