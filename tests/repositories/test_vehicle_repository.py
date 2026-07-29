import pytest
from decimal import Decimal
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.vehicle import VehicleCreate
from app.models.vehicle import VehicleCategory

@pytest.fixture
def vehicle_data():
    return VehicleCreate(
        make="Toyota",
        model="Camry",
        year=2023,
        vin="1HGBH41JXMN109186",
        category=VehicleCategory.SEDAN,
        price=Decimal("2500000.00"),
        quantity=5,
        color="White"
    )

@pytest.mark.asyncio
async def test_create_vehicle_returns_vehicle_with_id(db_session, vehicle_data):
    repo = VehicleRepository(db_session)
    vehicle = await repo.create(vehicle_data)
    assert vehicle.id is not None
    assert vehicle.make == "Toyota"
    assert vehicle.vin == "1HGBH41JXMN109186"

@pytest.mark.asyncio
async def test_get_vehicle_by_id_returns_correct_vehicle(db_session, vehicle_data):
    repo = VehicleRepository(db_session)
    created = await repo.create(vehicle_data)
    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id

@pytest.mark.asyncio
async def test_get_vehicle_by_nonexistent_id_returns_none(db_session):
    import uuid
    repo = VehicleRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None

@pytest.mark.asyncio
async def test_create_vehicle_with_duplicate_vin_raises_error(db_session, vehicle_data):
    from sqlalchemy.exc import IntegrityError
    repo = VehicleRepository(db_session)
    await repo.create(vehicle_data)
    with pytest.raises(IntegrityError):
        await repo.create(vehicle_data)