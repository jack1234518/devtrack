
import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

# Application environment: development, test, or production.
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

# Never use the development fallback in production.
_DEVELOPMENT_SECRET = (
    "devtrack-local-development-secret-change-before-deployment"
)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()

if not JWT_SECRET_KEY:
    if APP_ENV in {"development", "test"}:
        JWT_SECRET_KEY = _DEVELOPMENT_SECRET
    else:
        raise RuntimeError(
            "JWT_SECRET_KEY must be configured when running in production."
        )

if APP_ENV == "production":
    if len(JWT_SECRET_KEY) < 32:
        raise RuntimeError(
            "In production, JWT_SECRET_KEY must contain at least 32 characters."
        )

    if JWT_SECRET_KEY == _DEVELOPMENT_SECRET:
        raise RuntimeError(
            "The development JWT secret cannot be used in production."
        )

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password before it is stored in the database."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a submitted password against its stored hash."""
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int) -> str:
    """Create a signed JWT that expires after 30 minutes."""
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "type": "access",
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """Verify a JWT signature and its expiration."""
    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
    )

    if payload.get("type") != "access" or not payload.get("sub"):
        raise jwt.InvalidTokenError("Invalid access token")

    return payload
