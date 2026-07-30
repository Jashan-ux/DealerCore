import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from app.services.purchase_service import PurchaseService
from app.models.vehicle import Vehicle, VehicleCategory
from app.models.purchase import Purchase, PurchaseStatus
from app.models.user import User, UserRole


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def mock_vehicle_repo():
    return AsyncMock()


@pytest.fixture
def mock_purchase_repo():
    return AsyncMock()


@pytest.fixture
def purchase_service(mock_vehicle_repo, mock_purchase_repo):
    return PurchaseService(mock_vehicle_repo, mock_purchase_repo)


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


@pytest.fixture
def sample_user():
    u = User()
    u.id = uuid.uuid4()
    u.email = "buyer@example.com"
    u.role = UserRole.USER
    u.is_active = True
    return u


@pytest.fixture
def sample_purchase(sample_vehicle, sample_user):
    p = Purchase()
    p.id = uuid.uuid4()
    p.vehicle_id = sample_vehicle.id
    p.user_id = sample_user.id
    p.quantity_purchased = 2
    p.price_per_unit = Decimal("2500000.00")
    p.total_amount = Decimal("5000000.00")
    p.status = PurchaseStatus.COMPLETED
    return p


# ------------------------------------------------------------------ #
# Purchase creation tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_purchase_succeeds_when_stock_is_sufficient(
    purchase_service, mock_vehicle_repo, mock_purchase_repo,
    sample_vehicle, sample_purchase
):
    mock_vehicle_repo.get_by_id_with_lock.return_value = sample_vehicle
    mock_purchase_repo.create.return_value = sample_purchase

    result = await purchase_service.purchase_vehicle(
        vehicle_id=sample_vehicle.id,
        user_id=uuid.uuid4(),
        quantity=2
    )

    assert result.quantity_purchased == 2
    assert result.total_amount == Decimal("5000000.00")
    # Confirm the vehicle quantity was decremented before creating purchase
    assert sample_vehicle.quantity == 3


@pytest.mark.asyncio
async def test_purchase_raises_404_when_vehicle_not_found(
    purchase_service, mock_vehicle_repo
):
    mock_vehicle_repo.get_by_id_with_lock.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await purchase_service.purchase_vehicle(
            vehicle_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            quantity=1
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_purchase_raises_400_when_quantity_exceeds_stock(
    purchase_service, mock_vehicle_repo, sample_vehicle
):
    sample_vehicle.quantity = 3
    mock_vehicle_repo.get_by_id_with_lock.return_value = sample_vehicle

    with pytest.raises(HTTPException) as exc_info:
        await purchase_service.purchase_vehicle(
            vehicle_id=sample_vehicle.id,
            user_id=uuid.uuid4(),
            quantity=5   # requesting 5 but only 3 in stock
        )

    assert exc_info.value.status_code == 400
    assert "3" in exc_info.value.detail   # error message mentions available stock


@pytest.mark.asyncio
async def test_purchase_raises_400_when_stock_is_zero(
    purchase_service, mock_vehicle_repo, sample_vehicle
):
    sample_vehicle.quantity = 0
    mock_vehicle_repo.get_by_id_with_lock.return_value = sample_vehicle

    with pytest.raises(HTTPException) as exc_info:
        await purchase_service.purchase_vehicle(
            vehicle_id=sample_vehicle.id,
            user_id=uuid.uuid4(),
            quantity=1
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_purchase_calculates_total_correctly(
    purchase_service, mock_vehicle_repo, mock_purchase_repo,
    sample_vehicle, sample_purchase
):
    sample_vehicle.price = Decimal("1500000.00")
    sample_vehicle.quantity = 10
    mock_vehicle_repo.get_by_id_with_lock.return_value = sample_vehicle
    mock_purchase_repo.create.return_value = sample_purchase

    await purchase_service.purchase_vehicle(
        vehicle_id=sample_vehicle.id,
        user_id=uuid.uuid4(),
        quantity=3
    )

    # Verify the purchase was created with the correct total
    call_kwargs = mock_purchase_repo.create.call_args.kwargs
    assert call_kwargs["total_amount"] == Decimal("4500000.00")
    assert call_kwargs["price_per_unit"] == Decimal("1500000.00")


@pytest.mark.asyncio
async def test_purchase_decrements_vehicle_quantity(
    purchase_service, mock_vehicle_repo, mock_purchase_repo,
    sample_vehicle, sample_purchase
):
    sample_vehicle.quantity = 5
    mock_vehicle_repo.get_by_id_with_lock.return_value = sample_vehicle
    mock_purchase_repo.create.return_value = sample_purchase

    await purchase_service.purchase_vehicle(
        vehicle_id=sample_vehicle.id,
        user_id=uuid.uuid4(),
        quantity=3
    )

    assert sample_vehicle.quantity == 2


# ------------------------------------------------------------------ #
# Purchase history tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_get_my_purchases_returns_only_current_user_purchases(
    purchase_service, mock_purchase_repo, sample_purchase, sample_user
):
    mock_purchase_repo.get_by_user_id.return_value = [sample_purchase]
    mock_purchase_repo.count_by_user_id.return_value = 1

    result = await purchase_service.get_user_purchases(
        user_id=sample_user.id
    )

    assert len(result["items"]) == 1
    mock_purchase_repo.get_by_user_id.assert_called_once_with(
        sample_user.id, skip=0, limit=20
    )


@pytest.mark.asyncio
async def test_get_purchase_by_id_raises_404_if_not_found(
    purchase_service, mock_purchase_repo
):
    mock_purchase_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await purchase_service.get_purchase(uuid.uuid4())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_purchase_raises_403_if_user_does_not_own_it(
    purchase_service, mock_purchase_repo, sample_purchase, sample_user
):
    different_user_id = uuid.uuid4()
    mock_purchase_repo.get_by_id.return_value = sample_purchase

    with pytest.raises(HTTPException) as exc_info:
        await purchase_service.get_purchase(
            purchase_id=sample_purchase.id,
            requesting_user_id=different_user_id,
            is_admin=False   # not admin, so ownership matters
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_get_any_purchase(
    purchase_service, mock_purchase_repo, sample_purchase
):
    different_user_id = uuid.uuid4()  # admin is not the buyer
    mock_purchase_repo.get_by_id.return_value = sample_purchase

    # Should not raise any exception
    result = await purchase_service.get_purchase(
        purchase_id=sample_purchase.id,
        requesting_user_id=different_user_id,
        is_admin=True   # admin can see any purchase
    )

    assert result.id == sample_purchase.id