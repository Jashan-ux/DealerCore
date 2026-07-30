import pytest
import pytest_asyncio

SEARCH_URL = "/api/v1/vehicles/search"
VEHICLES_URL = "/api/v1/vehicles"


# ------------------------------------------------------------------ #
# Seed fixture: create vehicles via the API for realistic tests
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture(autouse=False)
async def seeded_inventory(client, admin_auth_headers):
    """
    Create a realistic inventory via the API.
    Using autouse=False means only tests that explicitly request
    this fixture will trigger the seeding.
    """
    vehicles = [
        {
            "make": "Toyota", "model": "Camry", "year": 2022,
            "vin": "APISRCH0000001ABC", "category": "sedan",
            "price": "2500000.00", "quantity": 5, "color": "White"
        },
        {
            "make": "Toyota", "model": "RAV4", "year": 2023,
            "vin": "APISRCH0000002DEF", "category": "suv",
            "price": "3200000.00", "quantity": 3, "color": "Black"
        },
        {
            "make": "Honda", "model": "Civic", "year": 2021,
            "vin": "APISRCH0000003GHI", "category": "sedan",
            "price": "1800000.00", "quantity": 0, "color": "Blue"
        },
        {
            "make": "Honda", "model": "CR-V", "year": 2023,
            "vin": "APISRCH0000004JKL", "category": "suv",
            "price": "2900000.00", "quantity": 7, "color": "Silver"
        },
        {
            "make": "Ford", "model": "F-150", "year": 2022,
            "vin": "APISRCH0000005MNO", "category": "truck",
            "price": "3800000.00", "quantity": 2, "color": "Red"
        },
        {
            "make": "Ford", "model": "Mustang", "year": 2023,
            "vin": "APISRCH0000006PQR", "category": "coupe",
            "price": "4500000.00", "quantity": 1, "color": "Black"
        },
    ]
    for v in vehicles:
        response = await client.post(VEHICLES_URL, json=v, headers=admin_auth_headers)
        assert response.status_code == 201, response.text

    return vehicles


# ------------------------------------------------------------------ #
# Endpoint availability tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_endpoint_exists_and_requires_auth(client):
    response = await client.get(SEARCH_URL)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_with_no_params_returns_200(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(SEARCH_URL, headers=user_auth_headers)
    assert response.status_code == 200


# ------------------------------------------------------------------ #
# Response structure tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_response_has_correct_structure(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(SEARCH_URL, headers=user_auth_headers)
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "total_pages" in data
    assert "has_next" in data
    assert "has_previous" in data


@pytest.mark.asyncio
async def test_search_default_pagination_values(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(SEARCH_URL, headers=user_auth_headers)
    data = response.json()

    assert data["page"] == 1
    assert data["per_page"] == 20
    assert data["has_previous"] is False


# ------------------------------------------------------------------ #
# Filter tests via HTTP
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_by_make_filters_correctly(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"make": "Toyota"},
        headers=user_auth_headers
    )
    data = response.json()

    assert data["total"] == 2
    assert all(v["make"] == "Toyota" for v in data["items"])


@pytest.mark.asyncio
async def test_search_by_category_filters_correctly(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"category": "suv"},
        headers=user_auth_headers
    )
    data = response.json()

    assert data["total"] == 2
    assert all(v["category"] == "suv" for v in data["items"])


@pytest.mark.asyncio
async def test_search_in_stock_only(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"in_stock": True},
        headers=user_auth_headers
    )
    data = response.json()

    assert all(v["quantity"] > 0 for v in data["items"])
    # Honda Civic has quantity=0, so 5 vehicles should be returned
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_search_by_price_range(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"price_min": "2000000", "price_max": "3500000"},
        headers=user_auth_headers
    )
    data = response.json()

    assert data["total"] == 3
    for item in data["items"]:
        assert float(item["price"]) >= 2000000
        assert float(item["price"]) <= 3500000


@pytest.mark.asyncio
async def test_search_multiple_filters_combine_with_and_logic(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"make": "Toyota", "category": "suv"},
        headers=user_auth_headers
    )
    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["model"] == "RAV4"


@pytest.mark.asyncio
async def test_search_returns_empty_for_no_matches(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"make": "Lamborghini"},
        headers=user_auth_headers
    )
    data = response.json()

    assert data["total"] == 0
    assert data["items"] == []


# ------------------------------------------------------------------ #
# Sort tests via HTTP
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_sort_by_price_asc(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"sort_by": "price", "sort_order": "asc"},
        headers=user_auth_headers
    )
    items = response.json()["items"]
    prices = [float(item["price"]) for item in items]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_search_sort_by_price_desc(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"sort_by": "price", "sort_order": "desc"},
        headers=user_auth_headers
    )
    items = response.json()["items"]
    prices = [float(item["price"]) for item in items]
    assert prices == sorted(prices, reverse=True)


@pytest.mark.asyncio
async def test_search_sort_by_year_desc(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"sort_by": "year", "sort_order": "desc"},
        headers=user_auth_headers
    )
    items = response.json()["items"]
    years = [item["year"] for item in items]
    assert years == sorted(years, reverse=True)


# ------------------------------------------------------------------ #
# Pagination tests via HTTP
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_pagination_page_1(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"page": 1, "per_page": 2, "sort_by": "price", "sort_order": "asc"},
        headers=user_auth_headers
    )
    data = response.json()

    assert len(data["items"]) == 2
    assert data["total"] == 6
    assert data["has_next"] is True
    assert data["has_previous"] is False
    assert data["total_pages"] == 3


@pytest.mark.asyncio
async def test_search_pagination_page_2(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"page": 2, "per_page": 2, "sort_by": "price", "sort_order": "asc"},
        headers=user_auth_headers
    )
    data = response.json()

    assert len(data["items"]) == 2
    assert data["has_next"] is True
    assert data["has_previous"] is True


@pytest.mark.asyncio
async def test_search_pagination_last_page(
    client, user_auth_headers, seeded_inventory
):
    response = await client.get(
        SEARCH_URL,
        params={"page": 3, "per_page": 2, "sort_by": "price", "sort_order": "asc"},
        headers=user_auth_headers
    )
    data = response.json()

    assert len(data["items"]) == 2
    assert data["has_next"] is False
    assert data["has_previous"] is True


@pytest.mark.asyncio
async def test_search_pages_do_not_overlap(
    client, user_auth_headers, seeded_inventory
):
    page1 = await client.get(
        SEARCH_URL,
        params={"page": 1, "per_page": 2, "sort_by": "price", "sort_order": "asc"},
        headers=user_auth_headers
    )
    page2 = await client.get(
        SEARCH_URL,
        params={"page": 2, "per_page": 2, "sort_by": "price", "sort_order": "asc"},
        headers=user_auth_headers
    )

    ids_page1 = {v["id"] for v in page1.json()["items"]}
    ids_page2 = {v["id"] for v in page2.json()["items"]}
    assert ids_page1.isdisjoint(ids_page2)


# ------------------------------------------------------------------ #
# Validation error tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_search_invalid_sort_by_returns_422(
    client, user_auth_headers
):
    response = await client.get(
        SEARCH_URL,
        params={"sort_by": "hacked_column; DROP TABLE vehicles;"},
        headers=user_auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_invalid_sort_order_returns_422(
    client, user_auth_headers
):
    response = await client.get(
        SEARCH_URL,
        params={"sort_order": "sideways"},
        headers=user_auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_invalid_year_range_returns_422(
    client, user_auth_headers
):
    response = await client.get(
        SEARCH_URL,
        params={"year_min": 2025, "year_max": 2020},
        headers=user_auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_invalid_price_range_returns_422(
    client, user_auth_headers
):
    response = await client.get(
        SEARCH_URL,
        params={"price_min": "5000000", "price_max": "1000000"},
        headers=user_auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_per_page_above_limit_returns_422(
    client, user_auth_headers
):
    response = await client.get(
        SEARCH_URL,
        params={"per_page": 500},
        headers=user_auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_page_zero_returns_422(
    client, user_auth_headers
):
    response = await client.get(
        SEARCH_URL,
        params={"page": 0},
        headers=user_auth_headers
    )
    assert response.status_code == 422