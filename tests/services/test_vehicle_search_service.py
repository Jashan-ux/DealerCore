import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

from app.services.vehicle_service import VehicleService
from app.schemas.search import VehicleSearchParams, PaginatedResponse
from app.models.vehicle import Vehicle, VehicleCategory


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_repo):
    return VehicleService(mock_repo)


def make_vehicle(make: str, price: Decimal, quantity: int) -> Vehicle:
    v = Vehicle()
    v.id = uuid.uuid4()
    v.make = make
    v.model = "TestModel"
    v.year = 2023
    v.vin = f"TEST{uuid.uuid4().hex[:13].upper()}"
    v.category = VehicleCategory.SEDAN
    v.price = price
    v.quantity = quantity
    v.is_deleted = False
    return v


@pytest.mark.asyncio
async def test_search_vehicles_returns_paginated_response(service, mock_repo):
    fake_vehicles = [
        make_vehicle("Toyota", Decimal("2500000.00"), 5),
        make_vehicle("Toyota", Decimal("3200000.00"), 3),
    ]
    mock_repo.search.return_value = (fake_vehicles, 2)

    params = VehicleSearchParams(make="Toyota")
    result = await service.search_vehicles(params)

    assert result.total == 2
    assert result.page == 1
    assert len(result.items) == 2
    assert result.has_next is False
    assert result.has_previous is False


@pytest.mark.asyncio
async def test_search_vehicles_calculates_has_next_correctly(service, mock_repo):
    fake_vehicles = [make_vehicle("Toyota", Decimal("2500000.00"), 5)]
    # total is 10 but only 1 item on page 1 of per_page=1
    mock_repo.search.return_value = (fake_vehicles, 10)

    params = VehicleSearchParams(page=1, per_page=1)
    result = await service.search_vehicles(params)

    assert result.has_next is True
    assert result.total_pages == 10


@pytest.mark.asyncio
async def test_search_vehicles_calculates_has_previous_correctly(service, mock_repo):
    fake_vehicles = [make_vehicle("Toyota", Decimal("2500000.00"), 5)]
    mock_repo.search.return_value = (fake_vehicles, 10)

    params = VehicleSearchParams(page=2, per_page=1)
    result = await service.search_vehicles(params)

    assert result.has_previous is True
    assert result.has_next is True


@pytest.mark.asyncio
async def test_search_vehicles_empty_results_returns_valid_response(service, mock_repo):
    mock_repo.search.return_value = ([], 0)

    params = VehicleSearchParams(make="Lamborghini")
    result = await service.search_vehicles(params)

    assert result.total == 0
    assert result.items == []
    assert result.has_next is False
    assert result.has_previous is False
    assert result.total_pages == 1  # always at least 1 page


@pytest.mark.asyncio
async def test_search_vehicles_passes_params_correctly_to_repo(service, mock_repo):
    mock_repo.search.return_value = ([], 0)

    params = VehicleSearchParams(
        make="Ford",
        category=VehicleCategory.TRUCK,
        in_stock=True,
        sort_by="price",
        sort_order="asc"
    )
    await service.search_vehicles(params)

    # Verify the repo was called with the exact params object
    mock_repo.search.assert_called_once_with(params)