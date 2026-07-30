import pytest
import asyncio
import uuid

BASE_URL = "/api/v1/purchases"


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

async def create_test_vehicle(client, admin_headers, quantity: int, vin: str):
    """Helper to create a vehicle and return its ID."""
    payload = {
        "make": "Toyota",
        "model": "Camry",
        "year": 2023,
        "vin": vin,
        "category": "sedan",
        "price": "2500000.00",
        "quantity": quantity,
        "color": "White"
    }
    response = await client.post(
        "/api/v1/vehicles",
        json=payload,
        headers=admin_headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ------------------------------------------------------------------ #
# Basic purchase tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_purchase_vehicle_returns_201_with_valid_data(
    client, admin_auth_headers, user_auth_headers
):
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=5, vin="1TESTVIN00000001A"
    )
    response = await client.post(
        BASE_URL,
        json={"vehicle_id": vehicle_id, "quantity": 2},
        headers=user_auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["quantity_purchased"] == 2
    assert data["status"] == "completed"
    assert "total_amount" in data
    assert "price_per_unit" in data


@pytest.mark.asyncio
async def test_purchase_reduces_vehicle_quantity(
    client, admin_auth_headers, user_auth_headers
):
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=5, vin="1TESTVIN00000002A"
    )
    await client.post(
        BASE_URL,
        json={"vehicle_id": vehicle_id, "quantity": 3},
        headers=user_auth_headers
    )
    # Check remaining quantity
    vehicle_response = await client.get(
        f"/api/v1/vehicles/{vehicle_id}",
        headers=user_auth_headers
    )
    assert vehicle_response.json()["quantity"] == 2


@pytest.mark.asyncio
async def test_purchase_nonexistent_vehicle_returns_404(
    client, user_auth_headers
):
    response = await client.post(
        BASE_URL,
        json={"vehicle_id": str(uuid.uuid4()), "quantity": 1},
        headers=user_auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_purchase_exceeding_stock_returns_400(
    client, admin_auth_headers, user_auth_headers
):
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=2, vin="1TESTVIN00000003A"
    )
    response = await client.post(
        BASE_URL,
        json={"vehicle_id": vehicle_id, "quantity": 5},
        headers=user_auth_headers
    )
    assert response.status_code == 400
    assert "2" in response.json()["detail"]


@pytest.mark.asyncio
async def test_purchase_out_of_stock_vehicle_returns_400(
    client, admin_auth_headers, user_auth_headers
):
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=0, vin="1TESTVIN00000004A"
    )
    response = await client.post(
        BASE_URL,
        json={"vehicle_id": vehicle_id, "quantity": 1},
        headers=user_auth_headers
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_purchase_without_authentication_returns_401(client):
    response = await client.post(
        BASE_URL,
        json={"vehicle_id": str(uuid.uuid4()), "quantity": 1}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_purchase_quantity_zero_returns_422(
    client, user_auth_headers
):
    response = await client.post(
        BASE_URL,
        json={"vehicle_id": str(uuid.uuid4()), "quantity": 0},
        headers=user_auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_purchase_negative_quantity_returns_422(
    client, user_auth_headers
):
    response = await client.post(
        BASE_URL,
        json={"vehicle_id": str(uuid.uuid4()), "quantity": -1},
        headers=user_auth_headers
    )
    assert response.status_code == 422


# ------------------------------------------------------------------ #
# THE critical concurrency test
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_concurrent_purchases_prevent_oversell(
    client, admin_auth_headers, user_auth_headers
):
    """
    This is the most important test in the entire kata.

    It simulates two users simultaneously trying to buy the last unit
    of a vehicle. With pessimistic locking in place, exactly one should
    succeed and exactly one should fail with a 400 error.

    Without locking, both would succeed and quantity would go negative,
    which the CHECK constraint would catch at the DB level — but by then
    the damage is done from a business perspective.

    asyncio.gather sends both requests concurrently in the same event loop,
    which is sufficient to trigger the race condition in practice.
    """
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=1,             # only ONE unit available
        vin="1TESTVIN00000005A"
    )

    purchase_payload = {"vehicle_id": vehicle_id, "quantity": 1}

    # Send both purchase requests concurrently
    results = await asyncio.gather(
        client.post(BASE_URL, json=purchase_payload, headers=user_auth_headers),
        client.post(BASE_URL, json=purchase_payload, headers=user_auth_headers),
        return_exceptions=True
    )

    # Filter out any unexpected exceptions
    responses = [r for r in results if hasattr(r, "status_code")]
    status_codes = [r.status_code for r in responses]

    # Exactly one must succeed and exactly one must fail
    assert status_codes.count(201) == 1, (
        f"Expected exactly 1 success, got: {status_codes}"
    )
    assert status_codes.count(400) == 1, (
        f"Expected exactly 1 failure, got: {status_codes}"
    )

    # Verify the vehicle quantity is now 0, not -1
    vehicle_response = await client.get(
        f"/api/v1/vehicles/{vehicle_id}",
        headers=user_auth_headers
    )
    assert vehicle_response.json()["quantity"] == 0


@pytest.mark.asyncio
async def test_concurrent_purchases_with_sufficient_stock_both_succeed(
    client, admin_auth_headers, user_auth_headers
):
    """
    Verify that locking does not break legitimate concurrent purchases
    when stock is sufficient for both requests.
    """
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=10,            # enough for both
        vin="1TESTVIN00000006A"
    )

    purchase_payload = {"vehicle_id": vehicle_id, "quantity": 3}

    results = await asyncio.gather(
        client.post(BASE_URL, json=purchase_payload, headers=user_auth_headers),
        client.post(BASE_URL, json=purchase_payload, headers=user_auth_headers),
        return_exceptions=True
    )

    status_codes = [r.status_code for r in results if hasattr(r, "status_code")]

    # Both should succeed
    assert status_codes.count(201) == 2, (
        f"Expected both to succeed, got: {status_codes}"
    )

    # Quantity should be 4 (10 - 3 - 3)
    vehicle_response = await client.get(
        f"/api/v1/vehicles/{vehicle_id}",
        headers=user_auth_headers
    )
    assert vehicle_response.json()["quantity"] == 4


# ------------------------------------------------------------------ #
# Purchase history tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_get_my_purchases_returns_own_purchases(
    client, admin_auth_headers, user_auth_headers
):
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=5, vin="1TESTVIN00000007A"
    )
    await client.post(
        BASE_URL,
        json={"vehicle_id": vehicle_id, "quantity": 1},
        headers=user_auth_headers
    )

    response = await client.get(
        f"{BASE_URL}/my",
        headers=user_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_admin_can_view_all_purchases(
    client, admin_auth_headers, user_auth_headers
):
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=5, vin="1TESTVIN00000008A"
    )
    await client.post(
        BASE_URL,
        json={"vehicle_id": vehicle_id, "quantity": 1},
        headers=user_auth_headers
    )

    response = await client.get(
        BASE_URL,
        headers=admin_auth_headers
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_regular_user_cannot_view_all_purchases(
    client, user_auth_headers
):
    response = await client.get(
        BASE_URL,
        headers=user_auth_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_purchase_by_id_as_owner_returns_200(
    client, admin_auth_headers, user_auth_headers
):
    vehicle_id = await create_test_vehicle(
        client, admin_auth_headers,
        quantity=5, vin="1TESTVIN00000009A"
    )
    purchase_resp = await client.post(
        BASE_URL,
        json={"vehicle_id": vehicle_id, "quantity": 1},
        headers=user_auth_headers
    )
    purchase_id = purchase_resp.json()["id"]

    response = await client.get(
        f"{BASE_URL}/{purchase_id}",
        headers=user_auth_headers
    )
    assert response.status_code == 200