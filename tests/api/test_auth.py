import pytest

BASE_URL = "/api/v1/auth"


# ------------------------------------------------------------------ #
# Registration tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_register_new_user_returns_201(client):
    payload = {
        "email": "alice@example.com",
        "password": "Secure123",
        "full_name": "Alice Smith"
    }
    response = await client.post(f"{BASE_URL}/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["role"] == "user"
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    payload = {
        "email": "bob@example.com",
        "password": "Secure123",
        "full_name": "Bob Jones"
    }
    await client.post(f"{BASE_URL}/register", json=payload)
    response = await client.post(f"{BASE_URL}/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password_returns_422(client):
    payload = {
        "email": "charlie@example.com",
        "password": "weak",   # too short, no uppercase, no digit
        "full_name": "Charlie"
    }
    response = await client.post(f"{BASE_URL}/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email_returns_422(client):
    payload = {
        "email": "not-an-email",
        "password": "Secure123",
        "full_name": "Dave"
    }
    response = await client.post(f"{BASE_URL}/register", json=payload)
    assert response.status_code == 422


# ------------------------------------------------------------------ #
# Login tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_login_with_correct_credentials_returns_tokens(client):
    # Register first
    await client.post(f"{BASE_URL}/register", json={
        "email": "eve@example.com",
        "password": "Secure123",
        "full_name": "Eve Wilson"
    })
    # Login
    response = await client.post(
        f"{BASE_URL}/login",
        data={"username": "eve@example.com", "password": "Secure123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    await client.post(f"{BASE_URL}/register", json={
        "email": "frank@example.com",
        "password": "Secure123",
        "full_name": "Frank"
    })
    response = await client.post(
        f"{BASE_URL}/login",
        data={"username": "frank@example.com", "password": "WrongPass1"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client):
    response = await client.post(
        f"{BASE_URL}/login",
        data={"username": "nobody@example.com", "password": "Secure123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 401


# ------------------------------------------------------------------ #
# Token refresh tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_refresh_with_valid_token_returns_new_access_token(client):
    await client.post(f"{BASE_URL}/register", json={
        "email": "grace@example.com",
        "password": "Secure123",
        "full_name": "Grace"
    })
    login_resp = await client.post(
        f"{BASE_URL}/login",
        data={"username": "grace@example.com", "password": "Secure123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    refresh_token = login_resp.json()["refresh_token"]

    response = await client.post(
        f"{BASE_URL}/refresh",
        json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_returns_401(client):
    response = await client.post(
        f"{BASE_URL}/refresh",
        json={"refresh_token": "this.is.not.a.valid.jwt"}
    )
    assert response.status_code == 401


# ------------------------------------------------------------------ #
# Protected route tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_accessing_protected_route_without_token_returns_401(client):
    import uuid
    response = await client.delete(f"/api/v1/vehicles/{uuid.uuid4()}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_accessing_admin_route_as_regular_user_returns_403(client):
    # Register and login as regular user
    await client.post(f"{BASE_URL}/register", json={
        "email": "henry@example.com",
        "password": "Secure123",
        "full_name": "Henry"
    })
    login_resp = await client.post(
        f"{BASE_URL}/login",
        data={"username": "henry@example.com", "password": "Secure123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    access_token = login_resp.json()["access_token"]
    import uuid
    response = await client.delete(
        f"/api/v1/vehicles/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    # 403 because user is authenticated but lacks admin role
    # (would be 404 if admin, but 403 check happens first)
    assert response.status_code == 403


# ------------------------------------------------------------------ #
# Logout tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_logout_then_refresh_returns_401(client):
    await client.post(f"{BASE_URL}/register", json={
        "email": "ivan@example.com",
        "password": "Secure123",
        "full_name": "Ivan"
    })
    login_resp = await client.post(
        f"{BASE_URL}/login",
        data={"username": "ivan@example.com", "password": "Secure123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Logout
    await client.post(
        f"{BASE_URL}/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"}
    )

    # Try to refresh after logout — should fail
    response = await client.post(
        f"{BASE_URL}/refresh",
        json={"refresh_token": refresh_token}
    )
    assert response.status_code == 401