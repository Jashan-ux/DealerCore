import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
import uuid
from app.services.vehicle_service import VehicleService
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from app.models.vehicle import Vehicle, VehicleCategory
from fastapi import HTTPException

@pytest.fixture
def mock_repo():
    return AsyncMock()

@pytest.fixture
def service(mock_repo):
    return VehicleService(mock_repo)

@pytest.fixture
def sample_vehicle():
    v = Vehicle()
    v.id = uuid.uuid4()
    v.make = "Toyota"
    v.model = "Camry"
    v.year = 2023
    v.vin = "1HGBH41JXMN109186"
    v.category = VehicleCategory.SEDAN
    v.price = Decimal("2500000.00")
    v.quantity = 5
    v.is_deleted = False
    return v

@pytest.mark.asyncio
async def test_create_vehicle_succeeds_when_vin_is_unique(service, mock_repo, sample_vehicle):
    mock_repo.get_by_vin.return_value = None  # VIN does not exist
    mock_repo.create.return_value = sample_vehicle
    data = VehicleCreate(
        make="Toyota", model="Camry", year=2023,
        vin="1HGBH41JXMN109186", category=VehicleCategory.SEDAN,
        price=Decimal("2500000.00"), quantity=5
    )
    result = await service.create_vehicle(data)
    assert result.make == "Toyota"
    mock_repo.create.assert_called_once()

@pytest.mark.asyncio
async def test_create_vehicle_raises_409_when_vin_exists(service, mock_repo, sample_vehicle):
    mock_repo.get_by_vin.return_value = sample_vehicle  # VIN already exists
    data = VehicleCreate(
        make="Toyota", model="Camry", year=2023,
        vin="1HGBH41JXMN109186", category=VehicleCategory.SEDAN,
        price=Decimal("2500000.00"), quantity=5
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.create_vehicle(data)
    assert exc_info.value.status_code == 409

@pytest.mark.asyncio
async def test_get_vehicle_raises_404_when_not_found(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_vehicle(uuid.uuid4())
    assert exc_info.value.status_code == 404