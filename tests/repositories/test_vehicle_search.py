import pytest
import pytest_asyncio
from decimal import Decimal

from app.models.vehicle import VehicleCategory
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.search import VehicleSearchParams
from app.schemas.vehicle import VehicleCreate


# ------------------------------------------------------------------ #
# Fixtures: seed several vehicles to search through
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture
async def seeded_vehicles(db_session):
    """
    Create a set of vehicles with varied attributes.
    Tests will search through this set and verify correct filtering.
    """
    repo = VehicleRepository(db_session)
    vehicles = []

    specs = [
        {
            "make": "Toyota", "model": "Camry", "year": 2022,
            "vin": "ABC12345678901234", "category": VehicleCategory.SEDAN,
            "price": Decimal("2500000.00"), "quantity": 5, "color": "White"
        },
        {
            "make": "Toyota", "model": "RAV4", "year": 2023,
            "vin": "XYZ98765432109876", "category": VehicleCategory.SUV,
            "price": Decimal("3200000.00"), "quantity": 3, "color": "Black"
        },
        {
            "make": "Honda", "model": "Civic", "year": 2021,
            "vin": "LMN45678901234567", "category": VehicleCategory.SEDAN,
            "price": Decimal("1800000.00"), "quantity": 0, "color": "Blue"
        },
        {
            "make": "Honda", "model": "CR-V", "year": 2023,
            "vin": "QRS34567890123456", "category": VehicleCategory.SUV,
            "price": Decimal("2900000.00"), "quantity": 7, "color": "Silver"
        },
        {
            "make": "Ford", "model": "F-150", "year": 2022,
            "vin": "TUV67890123456789", "category": VehicleCategory.TRUCK,
            "price": Decimal("3800000.00"), "quantity": 2, "color": "Red"
        },
        {
            "make": "Ford", "model": "Mustang", "year": 2023,
            "vin": "JKL23456789012345", "category": VehicleCategory.COUPE,
            "price": Decimal("4500000.00"), "quantity": 1, "color": "Black"
        },
    ]

    for spec in specs:
        vehicle = await repo.create(VehicleCreate(**spec))
        vehicles.append(vehicle)

    return vehicles


# ------------------------------------------------------------------ #
# Filter tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_by_make_returns_only_matching_vehicles(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(make="Toyota")
    items, total = await repo.search(params)

    assert total == 2
    assert all(v.make == "Toyota" for v in items)


@pytest.mark.asyncio
async def test_search_by_make_is_case_insensitive(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(make="toyota")
    items, total = await repo.search(params)

    assert total == 2


@pytest.mark.asyncio
async def test_search_by_partial_make_returns_matching_vehicles(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(make="toy")  # partial match
    items, total = await repo.search(params)

    assert total == 2


@pytest.mark.asyncio
async def test_search_by_category_returns_only_matching_vehicles(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(category=VehicleCategory.SEDAN)
    items, total = await repo.search(params)

    assert total == 2
    assert all(v.category == VehicleCategory.SEDAN for v in items)


@pytest.mark.asyncio
async def test_search_by_price_range_returns_correct_vehicles(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(
        price_min=Decimal("2000000.00"),
        price_max=Decimal("3500000.00")
    )
    items, total = await repo.search(params)

    # Camry (2.5M), RAV4 (3.2M), CR-V (2.9M) — three vehicles in range
    assert total == 3
    assert all(
        Decimal("2000000.00") <= v.price <= Decimal("3500000.00")
        for v in items
    )


@pytest.mark.asyncio
async def test_search_in_stock_only_excludes_zero_quantity(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(in_stock=True)
    items, total = await repo.search(params)

    # Honda Civic has quantity=0, so it should be excluded
    assert all(v.quantity > 0 for v in items)
    assert total == 5  # 6 total minus the 1 out of stock


@pytest.mark.asyncio
async def test_search_by_year_range_returns_correct_vehicles(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(year_min=2022, year_max=2022)
    items, total = await repo.search(params)

    assert total == 2  # Camry 2022 and F-150 2022
    assert all(v.year == 2022 for v in items)


@pytest.mark.asyncio
async def test_search_with_multiple_filters_combines_correctly(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(
        make="Toyota",
        category=VehicleCategory.SUV,
    )
    items, total = await repo.search(params)

    # Only Toyota RAV4 matches both filters
    assert total == 1
    assert items[0].model == "RAV4"


@pytest.mark.asyncio
async def test_search_with_no_filters_returns_all_vehicles(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams()
    items, total = await repo.search(params)

    assert total == 6


@pytest.mark.asyncio
async def test_search_returns_empty_when_no_matches(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(make="Lamborghini")
    items, total = await repo.search(params)

    assert total == 0
    assert items == []


# ------------------------------------------------------------------ #
# Sort tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_sort_by_price_ascending(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(sort_by="price", sort_order="asc")
    items, total = await repo.search(params)

    prices = [v.price for v in items]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_search_sort_by_price_descending(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(sort_by="price", sort_order="desc")
    items, total = await repo.search(params)

    prices = [v.price for v in items]
    assert prices == sorted(prices, reverse=True)


@pytest.mark.asyncio
async def test_search_sort_by_year_descending(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(sort_by="year", sort_order="desc")
    items, total = await repo.search(params)

    years = [v.year for v in items]
    assert years == sorted(years, reverse=True)


# ------------------------------------------------------------------ #
# Pagination tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_pagination_returns_correct_page_size(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    params = VehicleSearchParams(page=1, per_page=2)
    items, total = await repo.search(params)

    assert len(items) == 2
    assert total == 6  # total is always the full count, not just this page


@pytest.mark.asyncio
async def test_search_pagination_second_page_returns_next_items(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)

    params_page1 = VehicleSearchParams(
        page=1, per_page=2, sort_by="price", sort_order="asc"
    )
    params_page2 = VehicleSearchParams(
        page=2, per_page=2, sort_by="price", sort_order="asc"
    )

    items_page1, _ = await repo.search(params_page1)
    items_page2, _ = await repo.search(params_page2)

    # Pages should not overlap
    ids_page1 = {v.id for v in items_page1}
    ids_page2 = {v.id for v in items_page2}
    assert ids_page1.isdisjoint(ids_page2)

    # Page 1 prices should all be lower than page 2 prices
    max_price_page1 = max(v.price for v in items_page1)
    min_price_page2 = min(v.price for v in items_page2)
    assert max_price_page1 < min_price_page2


@pytest.mark.asyncio
async def test_search_last_page_returns_remaining_items(
    db_session, seeded_vehicles
):
    repo = VehicleRepository(db_session)
    # 6 vehicles, per_page=4, page=2 should return 2 items
    params = VehicleSearchParams(page=2, per_page=4)
    items, total = await repo.search(params)

    assert len(items) == 2
    assert total == 6
