import pytest
from decimal import Decimal

BASE_URL = "/api/v1/vehicles"

@pytest.mark.asyncio
async def test_create_vehicle_returns_201(client):
    payload = {
        "make": "Honda", "model": "Civic", "year": 2022,
        "vin": "2HGFG1B68CH500001", "category": "sedan",
        "price": "1800000.00", "quantity": 3, "color": "Blue"
    }
    response = await client.post(BASE_URL, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["vin"] == "2HGFG1B68CH500001"
    assert "id" in data

@pytest.mark.asyncio
async def test_create_vehicle_with_duplicate_vin_returns_409(client):
    payload = {
        "make": "Honda", "model": "Civic", "year": 2022,
        "vin": "2HGFG1B68CH500002", "category": "sedan",
        "price": "1800000.00", "quantity": 3
    }
    await client.post(BASE_URL, json=payload)
    response = await client.post(BASE_URL, json=payload)
    assert response.status_code == 409

@pytest.mark.asyncio
async def test_get_vehicle_returns_200(client):
    payload = {
        "make": "Ford", "model": "F-150", "year": 2023,
        "vin": "1FTFW1E83MFC00001", "category": "truck",
        "price": "3500000.00", "quantity": 2
    }
    create_response = await client.post(BASE_URL, json=payload)
    vehicle_id = create_response.json()["id"]
    response = await client.get(f"{BASE_URL}/{vehicle_id}")
    assert response.status_code == 200
    assert response.json()["model"] == "F-150"

@pytest.mark.asyncio
async def test_get_nonexistent_vehicle_returns_404(client):
    import uuid
    response = await client.get(f"{BASE_URL}/{uuid.uuid4()}")
    assert response.status_code == 404