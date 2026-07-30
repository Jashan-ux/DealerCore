import hashlib
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# CryptContext manages the hashing algorithm.
# bcrypt is the industry standard for password hashing because it is
# intentionally slow (making brute force attacks expensive) and
# includes a random salt automatically (preventing rainbow table attacks).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, role: str) -> str:
    """
    Create a short-lived JWT access token.
    The payload contains the user ID as 'sub' (subject),
    the role, expiry time, and a type field to distinguish
    access tokens from refresh tokens.
    """
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, datetime]:
    """
    Create a long-lived JWT refresh token.
    Returns both the token string and its expiry datetime,
    because the expiry datetime is stored in the database alongside
    the token hash.
    """
    expire = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, expire


def hash_token(token: str) -> str:
    """
    Hash a refresh token using SHA-256 before storing it in the database.
    We never store the raw token — only its hash.
    This means even if the refresh_tokens table is stolen,
    the attacker cannot use those hashes to authenticate.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    Raises ValueError if the token is invalid, expired, or tampered with.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")