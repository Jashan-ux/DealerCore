import pytest
import pytest_asyncio
import uuid
from decimal import Decimal

from app.models.vehicle import VehicleCategory
from app.repositories.purchase_repository import PurchaseRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.vehicle import VehicleCreate
from app.schemas.purchase import PurchaseCreate
from app.models.user import UserRole


# ------------------------------------------------------------------ #
# Shared fixtures for this test module
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture
async def sample_vehicle(db_session):
    """Create a real vehicle in the test DB for use in purchase tests."""
    repo = VehicleRepository(db_session)
    return await repo.create(VehicleCreate(
        make="Toyota",
        model="Camry",
        year=2023,
        vin="1HGBH41JXMN109186",
        category=VehicleCategory.SEDAN,
        price=Decimal("2500000.00"),
        quantity=5,
        color="White"
    ))


@pytest_asyncio.fixture
async def sample_user(db_session):
    """Create a real user in the test DB for use in purchase tests."""
    repo = UserRepository(db_session)
    from app.core.security import hash_password
    return await repo.create(
        email="buyer@example.com",
        hashed_password=hash_password("Secure123"),
        full_name="Test Buyer",
        role=UserRole.USER
    )


# ------------------------------------------------------------------ #
# Repository tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_create_purchase_returns_purchase_with_id(
    db_session, sample_vehicle, sample_user
):
    repo = PurchaseRepository(db_session)
    purchase = await repo.create(
        vehicle_id=sample_vehicle.id,
        user_id=sample_user.id,
        quantity=2,
        price_per_unit=sample_vehicle.price,
        total_amount=sample_vehicle.price * 2
    )
    assert purchase.id is not None
    assert purchase.quantity_purchased == 2
    assert purchase.total_amount == Decimal("5000000.00")


@pytest.mark.asyncio
async def test_get_purchase_by_id_returns_correct_record(
    db_session, sample_vehicle, sample_user
):
    repo = PurchaseRepository(db_session)
    created = await repo.create(
        vehicle_id=sample_vehicle.id,
        user_id=sample_user.id,
        quantity=1,
        price_per_unit=sample_vehicle.price,
        total_amount=sample_vehicle.price
    )
    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id


@pytest.mark.asyncio
async def test_get_purchases_by_user_returns_only_that_users_purchases(
    db_session, sample_vehicle, sample_user
):
    repo = PurchaseRepository(db_session)
    await repo.create(
        vehicle_id=sample_vehicle.id,
        user_id=sample_user.id,
        quantity=1,
        price_per_unit=sample_vehicle.price,
        total_amount=sample_vehicle.price
    )
    purchases = await repo.get_by_user_id(sample_user.id)
    assert len(purchases) >= 1
    assert all(p.user_id == sample_user.id for p in purchases)


@pytest.mark.asyncio
async def test_get_nonexistent_purchase_returns_none(db_session):
    repo = PurchaseRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None