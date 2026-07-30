import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from app.main import app
from app.db.dependencies import get_db
from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(settings.TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ------------------------------------------------------------------ #
# Auth helper fixtures — added in Sprint 2
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture(scope="function")
async def registered_user(client):
    """Register a standard user and return the response data."""
    payload = {
        "email": "testuser@example.com",
        "password": "Secure123",
        "full_name": "Test User",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture(scope="function")
async def user_tokens(client, registered_user):
    """Login as the standard user and return the tokens."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser@example.com", "password": "Secure123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response.json()


@pytest_asyncio.fixture(scope="function")
async def user_auth_headers(user_tokens):
    """Return Authorization headers for a standard user."""
    return {"Authorization": f"Bearer {user_tokens['access_token']}"}


@pytest_asyncio.fixture(scope="function")
async def registered_admin(client, db_session):
    """
    Register a user and promote them to admin.
    In a real scenario you would use a seed script or a direct DB insert.
    Here we register and then manually update the role via the same test DB session.
    """
    from app.repositories.user_repository import UserRepository
    from app.models.user import UserRole

    payload = {
        "email": "adminuser@example.com",
        "password": "Secure123",
        "full_name": "Admin User",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    user_data = response.json()

    repo = UserRepository(db_session)
    user = await repo.get_by_email("adminuser@example.com")
    if user is None:
        raise AssertionError("Admin user was not created successfully")
    await repo.update_role(user, UserRole.ADMIN)
    await db_session.commit()

    return user_data


@pytest_asyncio.fixture(scope="function")
async def admin_tokens(client, registered_admin):
    """Login as admin and return tokens."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "adminuser@example.com", "password": "Secure123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response.json()


@pytest_asyncio.fixture(scope="function")
async def admin_auth_headers(admin_tokens):
    """Return Authorization headers for an admin user."""
    return {"Authorization": f"Bearer {admin_tokens['access_token']}"}