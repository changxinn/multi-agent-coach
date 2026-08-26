"""
JWT service for token creation and validation.

Uses PyJWT library for token encoding/decoding.
"""
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from app.config import get_settings

settings = get_settings()


def create_access_token(user_data: Dict[str, Any]) -> str:
    """
    Create JWT access token.

    Args:
        user_data: Dict containing user information:
            - id: User ID (will be used as 'sub' claim)
            - email: User email
            - name: User name
            - role: User role (admin, staff, user)
            - user_image: Optional user image URL

    Returns:
        JWT token string

    Example:
        token = create_access_token({
            "id": 123,
            "email": "user@example.com",
            "name": "John Doe",
            "role": "admin",
            "user_image": "https://..."
        })
    """
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(hours=settings.JWT_EXPIRY_HOURS)

    payload = {
        "sub": str(user_data["id"]),  # Subject (user ID)
        "email": user_data["email"],
        "name": user_data["name"],
        "role": user_data.get("role", "user"),  # Include role, default to "user"
        "user_image": user_data.get("user_image"),
        "exp": expiry,
        "iat": now,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token


def validate_token(token: str) -> Dict[str, Any]:
    """
    Validate JWT token and return decoded payload.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict

    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "sub", "email"]},
    )

    return payload


def refresh_token(token: str) -> str:
    """
    Refresh JWT token with new expiry time.

    Args:
        token: Current JWT token

    Returns:
        New JWT token with updated expiry

    Raises:
        jwt.ExpiredSignatureError: Token has expired (cannot refresh)
        jwt.InvalidTokenError: Token is invalid
    """
    # Validate current token first
    payload = validate_token(token)

    # Create new token with same user data
    user_data = {
        "id": int(payload["sub"]),
        "email": payload["email"],
        "name": payload["name"],
        "role": payload.get("role", "user"),  # Preserve role from original token
        "user_image": payload.get("user_image"),
    }

    return create_access_token(user_data)
