"""
FastAPI dependency injection utilities for database sessions and authentication.
Supports both Firebase Authentication (RS256 ID tokens) and Local Authentication (HS256 tokens)
depending on system configuration (FIREBASE_AUTH_ENABLED).
Fails closed with no silent fallback in production.
"""
import re
import secrets
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

import jwt
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.core.security import decode_access_token
from app.core.firebase_auth import verify_firebase_id_token, FirebaseAuthError
from app.core.logging import get_logger

logger = get_logger(__name__)

# HTTP Bearer authentication scheme
security_bearer = HTTPBearer(auto_error=False)


def _generate_safe_username(db: Session, email: Optional[str], name: Optional[str], uid: str) -> str:
    """
    Generate a collision-safe, alphanumeric username (max 50 chars)
    for auto-provisioned Firebase users.
    """
    base = ""
    if name and isinstance(name, str) and name.strip():
        base = re.sub(r"[^a-zA-Z0-9_]", "", name.strip().lower().replace(" ", "_"))
    elif email and isinstance(email, str) and "@" in email:
        base = re.sub(r"[^a-zA-Z0-9_]", "", email.split("@")[0].strip().lower())

    if not base or len(base) < 3:
        base = "user"

    base = base[:20]
    candidate = f"{base}_{uid[:8]}"[:50]
    existing = db.query(User).filter(func.lower(User.username) == candidate.lower()).first()
    if not existing:
        return candidate

    # Incremental resolution with UID slices
    for i in range(8, 20):
        candidate = f"{base}_{uid[:i]}"[:50]
        if not db.query(User).filter(func.lower(User.username) == candidate.lower()).first():
            return candidate

    # Fallback with random hex suffix
    random_suffix = secrets.token_hex(4)
    return f"{base[:30]}_{random_suffix}"[:50]


def _provision_firebase_user(
    db: Session,
    uid: str,
    clean_email: str,
    name: Optional[str] = None
) -> User:
    """
    Safely auto-provision a new unprivileged user for a verified Firebase UID.
    Recovers from concurrent provisioning races (UniqueViolation on username or firebase_uid)
    by rolling back, checking for the concurrently created account by verified UID,
    and safely retrying with a collision-resistant username if only the username collided.
    """
    safe_username = _generate_safe_username(db, clean_email, name, uid)
    new_user = User(
        username=safe_username,
        email=clean_email,
        hashed_password=None,
        firebase_uid=uid,
        full_name=name if isinstance(name, str) else None,
        is_active=True,
        is_superuser=False,  # strictly non-administrator
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
        logger.info("Auto-provisioned new Firebase user: %s (uid=%s)", safe_username, uid[:10])
        return new_user
    except IntegrityError:
        db.rollback()
        # 1. Look up concurrently created account by verified Firebase UID
        existing_user = db.query(User).filter(User.firebase_uid == uid).first()
        if existing_user:
            if not existing_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is deactivated."
                )
            logger.info("Recovered from concurrent provisioning race; resolved user by UID: %s", existing_user.username)
            return existing_user

        # 2. Check if an account with this email was concurrently registered with a different UID
        existing_email_user = db.query(User).filter(func.lower(User.email) == clean_email.lower()).first()
        if existing_email_user and existing_email_user.firebase_uid != uid:
            logger.warning("Concurrently registered email collision: %s", clean_email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An existing account is already registered with this email address. "
                       "Please link your existing account with your password before signing in."
            )

        # 3. If UID does not exist and no email conflict, only username collided.
        # Safely retry with a collision-resistant unique username.
        suffix = secrets.token_hex(4)
        retry_username = f"{safe_username[:40]}_{suffix}"[:50]
        retry_user = User(
            username=retry_username,
            email=clean_email,
            hashed_password=None,
            firebase_uid=uid,
            full_name=name if isinstance(name, str) else None,
            is_active=True,
            is_superuser=False,
        )
        db.add(retry_user)
        try:
            db.commit()
            db.refresh(retry_user)
            logger.info("Recovered from username collision; provisioned with: %s", retry_username)
            return retry_user
        except Exception as retry_err:
            db.rollback()
            logger.error("Failed to provision Firebase user after username retry: %s", retry_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize user profile."
            )
    except Exception as e:
        db.rollback()
        logger.error("Failed to provision Firebase user: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize user profile."
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """
    Authenticate request via Bearer token and retrieve the active User record.
    - When FIREBASE_AUTH_ENABLED is True: verifies RS256 Firebase ID token against Google JWKS.
      Resolves user by verified firebase_uid. Auto-provisions new users if not found,
      rejecting ambiguous email collisions and never elevating privileges.
    - When FIREBASE_AUTH_ENABLED is False: verifies local HS256 development JWT.
    Fails closed immediately on missing, invalid, or expired credentials.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    settings = get_settings()

    # Detect RS256 token header to support verified Firebase Google tokens seamlessly
    is_firebase_token = False
    try:
        unverified_header = jwt.get_unverified_header(token)
        if unverified_header.get("alg") == "RS256":
            is_firebase_token = True
    except Exception:
        pass

    if settings.FIREBASE_AUTH_ENABLED or is_firebase_token:
        # =====================================================================
        # FIREBASE AUTHENTICATION MODE (Production Standard)
        # =====================================================================
        try:
            payload = verify_firebase_id_token(token)
        except FirebaseAuthError as e:
            logger.warning("Firebase token rejection: %s", e.message)
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Authentication failed: {e.message}",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            logger.warning("Unexpected error during Firebase token verification: %s", type(e).__name__)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: invalid token signature or claims.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        uid: Optional[str] = payload.get("sub")
        if not uid or not isinstance(uid, str) or not uid.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing valid subject identifier.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # 1. Resolve user by verified firebase_uid first
        user = db.query(User).filter(User.firebase_uid == uid).first()

        if user:
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is deactivated."
                )
            return user

        # 2. User not found by firebase_uid -> Safe auto-provisioning
        token_email = payload.get("email")
        if token_email and isinstance(token_email, str):
            clean_email = token_email.strip().lower()
            # Safety check: Never link an existing local account solely because its email matches!
            existing_email_user = db.query(User).filter(
                func.lower(User.email) == clean_email
            ).first()
            if existing_email_user:
                logger.warning(
                    "Rejected ambiguous auto-link: local user %s has email %s but different/no firebase_uid.",
                    existing_email_user.username,
                    clean_email
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An existing account is already registered with this email address. "
                           "Please sign in with your local password to link your Firebase account."
                )
        else:
            clean_email = f"{uid[:16]}@firebase.local"

        name = payload.get("name")
        return _provision_firebase_user(db=db, uid=uid, clean_email=clean_email, name=name)

    else:
        # =====================================================================
        # LOCAL AUTHENTICATION MODE (Development / Testing Only)
        # =====================================================================
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        username: Optional[str] = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing valid subject identifier.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user account does not exist.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated."
            )

        return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure the authenticated user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated."
        )
    return current_user

