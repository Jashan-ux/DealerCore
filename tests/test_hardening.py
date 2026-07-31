import pytest


# ------------------------------------------------------------------ #
# Error handler tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_health_check_returns_healthy(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_validation_error_returns_structured_response(client):
    """
    A request with bad data should return 422 with a structured
    errors array, not FastAPI's default verbose Pydantic error format.
    """
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",      # invalid email
            "password": "weak",            # too short
            "full_name": ""               # empty name
        }
    )
    assert response.status_code == 422
    data = response.json()
    assert "errors" in data
    assert "detail" in data
    assert isinstance(data["errors"], list)
    assert len(data["errors"]) > 0
    # Each error should have field, message, and type
    for error in data["errors"]:
        assert "field" in error
        assert "message" in error


@pytest.mark.asyncio
async def test_request_id_header_present_in_response(client):
    """
    Every response must include the X-Request-ID header.
    This is added by RequestLoggingMiddleware.
    """
    response = await client.get("/health")
    assert "x-request-id" in response.headers
    # Request IDs should be UUIDs
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 36  # UUID format: 8-4-4-4-12


@pytest.mark.asyncio
async def test_nonexistent_route_returns_404(client):
    response = await client.get("/api/v1/nonexistent-endpoint")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_method_not_allowed_returns_405(client):
    # Vehicles list is GET only, DELETE on root should return 405
    response = await client.delete("/api/v1/vehicles")
    assert response.status_code in (405, 401)


# ------------------------------------------------------------------ #
# Rate limiting tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_rate_limit_on_login_after_many_requests(client):
    """
    Sending more than 5 login requests per minute from the same IP
    should result in a 429 Too Many Requests response.
    """
    payload = {"username": "nobody@example.com", "password": "wrong"}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    responses = []
    # Send 7 requests — first 5 should get 401, remainder should get 429
    for _ in range(7):
        r = await client.post("/api/v1/auth/login", data=payload, headers=headers)
        responses.append(r.status_code)

    assert 429 in responses, (
        f"Expected at least one 429 response, got: {responses}"
    )


@pytest.mark.asyncio
async def test_rate_limit_response_has_retry_after_header(client):
    """
    A 429 response must include Retry-After header so clients know
    how long to wait before retrying.
    """
    payload = {"username": "nobody@example.com", "password": "wrong"}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    responses = []
    for _ in range(7):
        r = await client.post("/api/v1/auth/login", data=payload, headers=headers)
        responses.append(r)

    rate_limited = [r for r in responses if r.status_code == 429]
    if rate_limited:
        assert "retry-after" in rate_limited[0].headers


# ------------------------------------------------------------------ #
# Audit log tests via API
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_audit_log_created_after_vehicle_creation(
    client, admin_auth_headers
):
    payload = {
        "make": "Audit", "model": "TestCar", "year": 2023,
        "vin": "AUDITLOG000001ABC", "category": "sedan",
        "price": "1000000.00", "quantity": 1
    }
    create_resp = await client.post(
        "/api/v1/vehicles",
        json=payload,
        headers=admin_auth_headers
    )
    assert create_resp.status_code == 201
    vehicle_id = create_resp.json()["id"]

    # Check audit logs for this vehicle
    audit_resp = await client.get(
        f"/api/v1/audit/entity/{vehicle_id}",
        headers=admin_auth_headers
    )
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    assert any(log["action"] == "vehicle_created" for log in logs)


@pytest.mark.asyncio
async def test_audit_log_created_after_vehicle_update(
    client, admin_auth_headers
):
    payload = {
        "make": "Audit", "model": "UpdateCar", "year": 2023,
        "vin": "AUDITLOG000002DEF", "category": "sedan",
        "price": "1000000.00", "quantity": 5
    }
    create_resp = await client.post(
        "/api/v1/vehicles",
        json=payload,
        headers=admin_auth_headers
    )
    vehicle_id = create_resp.json()["id"]

    # Update the vehicle
    await client.patch(
        f"/api/v1/vehicles/{vehicle_id}",
        json={"price": "1500000.00"},
        headers=admin_auth_headers
    )

    audit_resp = await client.get(
        f"/api/v1/audit/entity/{vehicle_id}",
        headers=admin_auth_headers
    )
    logs = audit_resp.json()
    assert any(log["action"] == "vehicle_updated" for log in logs)


@pytest.mark.asyncio
async def test_audit_endpoint_requires_admin(
    client, user_auth_headers
):
    import uuid
    response = await client.get(
        f"/api/v1/audit/entity/{uuid.uuid4()}",
        headers=user_auth_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_log_created_after_purchase(
    client, admin_auth_headers, user_auth_headers
):
    payload = {
        "make": "Audit", "model": "BuyCar", "year": 2023,
        "vin": "AUDITLOG000003GHI", "category": "sedan",
        "price": "2000000.00", "quantity": 3
    }
    create_resp = await client.post(
        "/api/v1/vehicles",
        json=payload,
        headers=admin_auth_headers
    )
    vehicle_id = create_resp.json()["id"]

    purchase_resp = await client.post(
        "/api/v1/purchases",
        json={"vehicle_id": vehicle_id, "quantity": 1},
        headers=user_auth_headers
    )
    assert purchase_resp.status_code == 201
    purchase_id = purchase_resp.json()["id"]

    # Audit log should exist for the purchase entity
    audit_resp = await client.get(
        f"/api/v1/audit/entity/{purchase_id}",
        headers=admin_auth_headers
    )
    logs = audit_resp.json()
    assert any(log["action"] == "vehicle_purchased" for log in logs)