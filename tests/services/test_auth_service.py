import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.services.auth_service import AuthService
from app.models.user import User, UserRole, RefreshToken
from app.schemas.user import UserRegister


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def mock_user_repo():
    return AsyncMock()


@pytest.fixture
def auth_service(mock_user_repo):
    return AuthService(mock_user_repo)


@pytest.fixture
def sample_user():
    user = User()
    user.id = uuid.uuid4()
    user.email = "john@example.com"
    user.full_name = "John Doe"
    user.role = UserRole.USER
    user.is_active = True
    # Bcrypt hash of "Password1"
    user.hashed_password = "$2b$12$KIXvC3V0Kh1kZ4oLgjYSsuGq4Kh1kZ4oLgjYSsuGq4Kh1kZ4oLgjY"
    return user


# ------------------------------------------------------------------ #
# Registration tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_register_succeeds_when_email_is_new(auth_service, mock_user_repo, sample_user):
    mock_user_repo.get_by_email.return_value = None  # email not taken
    mock_user_repo.create.return_value = sample_user

    data = UserRegister(
        email="john@example.com",
        password="Password1",
        full_name="John Doe"
    )
    result = await auth_service.register(data)

    assert result.email == "john@example.com"
    mock_user_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_register_raises_409_when_email_already_exists(auth_service, mock_user_repo, sample_user):
    mock_user_repo.get_by_email.return_value = sample_user  # email is taken

    data = UserRegister(
        email="john@example.com",
        password="Password1",
        full_name="John Doe"
    )
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register(data)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_register_stores_hashed_password_not_plain_text(auth_service, mock_user_repo, sample_user):
    mock_user_repo.get_by_email.return_value = None
    mock_user_repo.create.return_value = sample_user

    data = UserRegister(
        email="john@example.com",
        password="Password1",
        full_name="John Doe"
    )
    await auth_service.register(data)

    # Extract what was actually passed to repo.create
    call_kwargs = mock_user_repo.create.call_args.kwargs
    assert call_kwargs["hashed_password"] != "Password1"
    assert call_kwargs["hashed_password"].startswith("$2b$")  # bcrypt prefix


# ------------------------------------------------------------------ #
# Login tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_login_returns_tokens_with_correct_credentials(auth_service, mock_user_repo, sample_user):
    mock_user_repo.get_by_email.return_value = sample_user
    mock_user_repo.create_refresh_token.return_value = MagicMock()

    with patch("app.services.auth_service.verify_password", return_value=True):
        result = await auth_service.login("john@example.com", "Password1")

    assert "access_token" in result
    assert "refresh_token" in result


@pytest.mark.asyncio
async def test_login_raises_401_when_user_not_found(auth_service, mock_user_repo):
    mock_user_repo.get_by_email.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("nobody@example.com", "Password1")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_raises_401_when_password_is_wrong(auth_service, mock_user_repo, sample_user):
    mock_user_repo.get_by_email.return_value = sample_user

    with patch("app.services.auth_service.verify_password", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login("john@example.com", "WrongPassword")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_raises_401_when_account_is_inactive(auth_service, mock_user_repo, sample_user):
    sample_user.is_active = False
    mock_user_repo.get_by_email.return_value = sample_user

    with patch("app.services.auth_service.verify_password", return_value=True):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login("john@example.com", "Password1")

    assert exc_info.value.status_code == 401


# ------------------------------------------------------------------ #
# Refresh token tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(auth_service, mock_user_repo, sample_user):
    mock_token_record = MagicMock()
    mock_token_record.is_revoked = False
    mock_token_record.expires_at = datetime.utcnow() + timedelta(days=6)
    mock_token_record.user_id = sample_user.id

    mock_user_repo.get_refresh_token_by_hash.return_value = mock_token_record
    mock_user_repo.get_by_id.return_value = sample_user

    with patch("app.services.auth_service.decode_token") as mock_decode:
        mock_decode.return_value = {
            "sub": str(sample_user.id),
            "type": "refresh"
        }
        result = await auth_service.refresh_access_token("valid_refresh_token")

    assert "access_token" in result


@pytest.mark.asyncio
async def test_refresh_raises_401_when_token_is_revoked(auth_service, mock_user_repo):
    mock_token_record = MagicMock()
    mock_token_record.is_revoked = True

    mock_user_repo.get_refresh_token_by_hash.return_value = mock_token_record

    with patch("app.services.auth_service.decode_token") as mock_decode:
        mock_decode.return_value = {"sub": str(uuid.uuid4()), "type": "refresh"}
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_access_token("revoked_token")

    assert exc_info.value.status_code == 401


# ------------------------------------------------------------------ #
# Logout tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(auth_service, mock_user_repo):
    with patch("app.services.auth_service.decode_token") as mock_decode:
        mock_decode.return_value = {"sub": str(uuid.uuid4()), "type": "refresh"}
        await auth_service.logout("any_refresh_token")

    mock_user_repo.revoke_refresh_token.assert_called_once()