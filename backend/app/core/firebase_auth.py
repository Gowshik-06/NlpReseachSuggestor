"""
Firebase Authentication Token Verification Module.

Verifies Firebase ID tokens using Google's published JWKS endpoints.
Enforces:
- RS256 cryptographic signature against Google's public signing keys
- Bounded, cached signing-key retrieval
- Project audience matching (FIREBASE_PROJECT_ID)
- Issuer validation (https://securetoken.google.com/<project_id>)
- Expiration, issued-at, and auth_time validity
- Valid, non-empty, bounded subject/UID
- Fail-closed behavior on network failures, expired tokens, or malformed payloads
- Zero logging of raw tokens or sensitive client credentials
"""
import time
from typing import Optional, Dict, Any
import jwt
from jwt.exceptions import (
    PyJWKClientError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidAlgorithmError,
    InvalidTokenError,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GOOGLE_JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"


class FirebaseAuthError(Exception):
    """Base exception for Firebase token validation errors."""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class FirebaseTokenVerifier:
    """
    Thread-safe, bounded-cache Firebase ID token verifier using PyJWKClient.
    """
    def __init__(
        self,
        jwks_url: str = GOOGLE_JWKS_URL,
        jwk_client: Optional[jwt.PyJWKClient] = None,
        max_cached_keys: int = 32,
        lifespan: int = 3600,
        timeout: int = 10,
    ):
        self.jwks_url = jwks_url
        if jwk_client is not None:
            self._jwk_client = jwk_client
        else:
            self._jwk_client = jwt.PyJWKClient(
                uri=self.jwks_url,
                cache_keys=True,
                max_cached_keys=max_cached_keys,
                cache_jwk_set=True,
                lifespan=lifespan,
                timeout=timeout,
            )

    @property
    def jwk_client(self) -> jwt.PyJWKClient:
        return self._jwk_client

    def verify_token(
        self,
        token: str,
        project_id: Optional[str] = None,
        clock_skew_seconds: int = 10,
    ) -> Dict[str, Any]:
        """
        Validate Firebase ID token and return its verified claims.
        Fails closed on any signature, audience, issuer, timing, or structural defect.
        """
        if not token or not isinstance(token, str) or not token.strip():
            raise FirebaseAuthError("Authentication token is missing or empty.")

        token = token.strip()
        settings = get_settings()
        target_project = project_id or settings.FIREBASE_PROJECT_ID

        if not target_project or not target_project.strip():
            logger.error("FIREBASE_PROJECT_ID is not configured.")
            raise FirebaseAuthError("Firebase authentication service is misconfigured on backend.", status_code=500)

        target_project = target_project.strip()
        expected_issuer = f"https://securetoken.google.com/{target_project}"

        # 1. Inspect unverified headers safely to check algorithm
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            logger.warning("Failed to decode token header: %s", type(e).__name__)
            raise FirebaseAuthError("Malformed authentication token header.")

        alg = unverified_header.get("alg")
        if alg != "RS256":
            logger.warning("Rejected token with invalid algorithm: %s", alg)
            raise FirebaseAuthError(f"Unsupported token algorithm '{alg}'. RS256 signature required.")

        kid = unverified_header.get("kid")
        if not kid or not isinstance(kid, str) or not kid.strip():
            logger.warning("Token missing key ID (kid) in header.")
            raise FirebaseAuthError("Token missing key identifier in header.")

        # 2. Retrieve signing key from JWKS
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
        except PyJWKClientError as e:
            logger.warning("JWKS key lookup failed for kid: %s", type(e).__name__)
            raise FirebaseAuthError("Unable to verify token against trusted Firebase signing keys.")
        except Exception as e:
            logger.warning("Unexpected error during JWKS lookup: %s", type(e).__name__)
            raise FirebaseAuthError("Token signing key retrieval failed.")

        # 3. Cryptographically verify signature, claims, audience, issuer, expiration
        try:
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=target_project,
                issuer=expected_issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "require": ["exp", "iat", "aud", "iss", "sub"],
                },
                leeway=clock_skew_seconds,
            )
        except ExpiredSignatureError:
            raise FirebaseAuthError("Firebase authentication token has expired.")
        except InvalidAudienceError:
            logger.warning("Firebase token audience mismatch.")
            raise FirebaseAuthError("Firebase token audience does not match expected project.")
        except InvalidIssuerError:
            logger.warning("Firebase token issuer mismatch.")
            raise FirebaseAuthError("Firebase token issuer is invalid.")
        except InvalidAlgorithmError:
            raise FirebaseAuthError("Invalid token signing algorithm.")
        except InvalidTokenError as e:
            logger.warning("Token validation failed: %s", type(e).__name__)
            raise FirebaseAuthError("Invalid or corrupted authentication token.")

        # 4. Enforce subject (UID) constraints
        sub = payload.get("sub")
        if not sub or not isinstance(sub, str) or not sub.strip():
            raise FirebaseAuthError("Firebase token missing valid subject (UID).")
        if len(sub) > 128:
            raise FirebaseAuthError("Firebase token subject (UID) exceeds maximum allowable length.")

        # 5. Enforce auth_time constraint if present
        auth_time = payload.get("auth_time")
        now = time.time()
        if auth_time is not None:
            if not isinstance(auth_time, (int, float)):
                raise FirebaseAuthError("Invalid auth_time format in token.")
            if auth_time > (now + clock_skew_seconds + 300):
                raise FirebaseAuthError("Authentication timestamp is in the future.")

        # 6. Enforce iat not in unreasonable future
        iat = payload.get("iat")
        if iat is not None and isinstance(iat, (int, float)):
            if iat > (now + clock_skew_seconds + 300):
                raise FirebaseAuthError("Token issued-at timestamp is in the future.")

        return payload


# Global singleton verifier
_default_verifier: Optional[FirebaseTokenVerifier] = None


def get_firebase_verifier() -> FirebaseTokenVerifier:
    """Return the global FirebaseTokenVerifier instance."""
    global _default_verifier
    if _default_verifier is None:
        _default_verifier = FirebaseTokenVerifier()
    return _default_verifier


def set_firebase_verifier(verifier: Optional[FirebaseTokenVerifier]) -> None:
    """Override or reset the global verifier (useful for tests)."""
    global _default_verifier
    _default_verifier = verifier


def verify_firebase_id_token(
    token: str,
    project_id: Optional[str] = None,
    verifier: Optional[FirebaseTokenVerifier] = None,
) -> Dict[str, Any]:
    """
    Convenience function to verify a Firebase ID token.
    Returns verified payload dict or raises FirebaseAuthError.
    """
    active_verifier = verifier or get_firebase_verifier()
    return active_verifier.verify_token(token=token, project_id=project_id)
