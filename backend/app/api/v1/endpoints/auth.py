"""
Authentication endpoints: Registration, Login, Firebase Authentication, and Account Linking.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    FirebaseLoginRequest,
    LinkFirebaseAccountRequest,
    LinkFirebaseAccountResponse,
)
from app.core.security import hash_password, verify_password, create_access_token
from app.api.deps import get_current_user, _generate_safe_username, _provision_firebase_user
from app.core.firebase_auth import verify_firebase_id_token, FirebaseAuthError
from app.core.logging import get_logger
from app.core.rate_limit import limiter

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, summary="Register New User")
def register(
    req: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new local user account with secure password hashing.
    Rejects duplicate usernames or emails. Returns JWT access token upon successful registration.
    Disabled when FIREBASE_AUTH_ENABLED is True to prevent unverified local account creation.
    """
    current_settings = get_settings()
    if current_settings.FIREBASE_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct local registration is disabled. Google Sign-In is the sole supported authentication method. "
                   "Please sign in via Google."
        )

    normalized_username = req.username.strip()
    normalized_email = req.email.strip().lower()

    # Check for existing username (case-insensitive)
    existing_user = db.query(User).filter(
        func.lower(User.username) == normalized_username.lower()
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken."
        )

    # Check for existing email (case-insensitive)
    existing_email = db.query(User).filter(
        func.lower(User.email) == normalized_email
    ).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered."
        )

    # Hash password securely
    hashed = hash_password(req.password)
    user = User(
        username=normalized_username,
        email=normalized_email,
        hashed_password=hashed,
        full_name=req.full_name.strip() if req.full_name else None,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("Registered new local user: %s (id=%d)", user.username, user.id)

    # Generate access token
    access_token = create_access_token(user.username)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse, summary="Authenticate User & Obtain Token")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    req: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate with username (or email) and password with rate limiting protection.
    Returns a signed JWT access token upon success in local authentication mode.
    Disabled when FIREBASE_AUTH_ENABLED is True to fail closed against unverified credentials.
    """
    current_settings = get_settings()
    if current_settings.FIREBASE_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct password login is disabled. Google Sign-In is the sole supported authentication method. "
                   "Please authenticate via Google."
        )

    login_identifier = req.username.strip().lower()

    user = db.query(User).filter(
        (func.lower(User.username) == login_identifier) |
        (func.lower(User.email) == login_identifier)
    ).first()

    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        # Consistent error message without revealing whether username existed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated."
        )

    logger.info("User logged in successfully: %s", user.username)

    access_token = create_access_token(user.username)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/firebase-login", response_model=TokenResponse, summary="Verify Firebase ID Token & Return Profile")
def firebase_login(
    req: FirebaseLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate or provision a user from a verified Firebase ID token.
    Validates token cryptographically, resolves user by firebase_uid,
    or auto-provisions a safe non-admin account if new.
    """
    try:
        payload = verify_firebase_id_token(req.id_token)
    except FirebaseAuthError as e:
        logger.warning("Firebase login token rejected: %s", e.message)
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Firebase authentication failed: {e.message}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.warning("Unexpected error during Firebase login: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unverified Firebase token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    uid = payload.get("sub")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token missing subject identifier."
        )

    # 1. Resolve by firebase_uid
    user = db.query(User).filter(User.firebase_uid == uid).first()
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated."
            )
        return TokenResponse(
            access_token=req.id_token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )

    # 2. Check email collision with existing local accounts
    token_email = payload.get("email")
    if token_email and isinstance(token_email, str):
        clean_email = token_email.strip().lower()
        existing_email_user = db.query(User).filter(
            func.lower(User.email) == clean_email
        ).first()
        if existing_email_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An existing account is already registered with this email address. "
                       "Please link your existing account with your password before signing in."
            )
    else:
        clean_email = f"{uid[:16]}@firebase.local"

    # 3. Auto-provision new unprivileged user with race condition recovery
    name = payload.get("name")
    user = _provision_firebase_user(db=db, uid=uid, clean_email=clean_email, name=name)
    return TokenResponse(
        access_token=req.id_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/link-firebase", response_model=LinkFirebaseAccountResponse, summary="Link Existing Local Account to Firebase")
def link_firebase_account(
    req: LinkFirebaseAccountRequest,
    db: Session = Depends(get_db)
):
    """
    Safely link an existing local account to a Firebase identity.
    Requires:
    1. Valid local account credentials (username/email + local password) proving control of local account.
    2. Valid, verified Firebase ID token proving control of the Firebase identity.
    3. Rejects conflicts if Firebase UID is already linked to another account.
    4. Rejects conflicts if local account is already linked to a different Firebase UID.
    5. Preserves existing local username, primary key, and administrator status.
    """
    # 1. Identify local user to link
    if not req.username_or_email or not req.username_or_email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is required to identify the local account to link."
        )

    identifier = req.username_or_email.strip().lower()
    user = db.query(User).filter(
        (func.lower(User.username) == identifier) |
        (func.lower(User.email) == identifier)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local user account not found."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local account is deactivated."
        )

    # 2. Prove control of local account via password
    if not user.hashed_password or not verify_password(req.local_password, user.hashed_password):
        logger.warning("Account linking rejected: invalid local password for user %s", user.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid local account password. Account linking requires valid credentials."
        )

    # 3. Verify Firebase token proving control of Firebase identity
    try:
        payload = verify_firebase_id_token(req.firebase_token)
    except FirebaseAuthError as e:
        logger.warning("Account linking rejected: invalid Firebase token: %s", e.message)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase credentials: {e.message}"
        )
    except Exception as e:
        logger.warning("Account linking token verification error: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to verify Firebase identity."
        )

    target_uid = payload.get("sub")
    if not target_uid or not isinstance(target_uid, str) or not target_uid.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token missing subject identifier."
        )

    # 4. Check if target_uid is already linked to another local account
    other_user = db.query(User).filter(
        (User.firebase_uid == target_uid) & (User.id != user.id)
    ).first()
    if other_user:
        logger.warning(
            "Account linking conflict: Firebase UID %s is already linked to user %s (id=%d)",
            target_uid, other_user.username, other_user.id
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Firebase identity is already linked to another ResearchLens account."
        )

    # 5. Check if local account is already linked to a different Firebase UID
    if user.firebase_uid and user.firebase_uid != target_uid:
        logger.warning(
            "Account linking conflict: User %s already linked to different Firebase UID %s",
            user.username, user.firebase_uid
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This ResearchLens account is already linked to a different Firebase identity."
        )

    # 6. Bind the Firebase UID safely
    user.firebase_uid = target_uid
    try:
        db.commit()
        db.refresh(user)
        logger.info(
            "Successfully linked local user %s (id=%d) to Firebase UID %s",
            user.username, user.id, target_uid
        )
        return LinkFirebaseAccountResponse(
            status="success",
            message=f"Account '{user.username}' successfully linked to Firebase identity.",
            user=UserResponse.model_validate(user)
        )
    except Exception as e:
        db.rollback()
        logger.error("Failed to commit account link: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record account link in database."
        )


@router.get("/me", response_model=UserResponse, summary="Get Current Authenticated User")
def get_me(
    current_user: User = Depends(get_current_user)
):
    """Retrieve profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
