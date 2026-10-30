"""
Authentication and security utilities: password hashing (bcrypt) and JWT signing/verification.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import jwt

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def hash_password(password: str) -> str:
    """Hash plaintext password securely using bcrypt with a unique salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.warning("Password verification error: %s", e)
        return False


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT access token with subject and expiration."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }
    encoded = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT access token signature and expiration."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Access token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid access token: %s", e)
        return None
