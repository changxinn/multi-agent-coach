"""
Authentication routes: login, register, token refresh.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt

from app.db.database import get_db
from app.db.repositories.user_repo import UserRepository
from app.services.jwt_service import create_access_token, refresh_token, validate_token
from app.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login with email and password.

    Returns JWT token if credentials are valid.
    """
    user_repo = UserRepository(db)

    # Find user by email
    user = await user_repo.get_by_email(request.email)

    if not user:
        logger.warning("Login attempt for non-existent user: %s", request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password with bcrypt
    if not bcrypt.checkpw(request.password.encode("utf-8"), user.password.encode("utf-8")):
        logger.warning("Invalid password for user: %s", request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if user is enabled
    if not user.enabled:
        logger.warning("Login attempt for disabled user: %s", request.email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Create JWT token with role (default to USER if not set)
    user_role = user.role.lower() if user.role else "user"
    token = create_access_token({
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user_role,  # Include role in token
        "user_image": None,
    })

    logger.info("User logged in successfully: %s (role: %s)", user.email, user_role)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "user_image": None,
            "role": user_role,
        },
    )


@router.post("/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.

    Creates user with role='USER' by default.
    Returns JWT token.
    """
    user_repo = UserRepository(db)

    # Check if email already exists
    existing_user = await user_repo.get_by_email(request.email)
    if existing_user:
        logger.warning("Registration attempt with existing email: %s", request.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password with bcrypt
    password_hash = bcrypt.hashpw(
        request.password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")

    # Create user
    user = await user_repo.create_user(
        email=request.email,
        password=password_hash,
        name=request.name,
        role="USER",  # Default role
    )

    logger.info("New user registered: %s (ID: %d)", user.email, user.id)

    # Create JWT token with role (new users default to USER)
    user_role = "user"  # Default role for new users
    token = create_access_token({
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user_role,
        "user_image": None,
    })

    logger.info("New user registered: %s (ID: %d, role: %s)", user.email, user.id, user_role)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "user_image": None,
            "role": user_role,
        },
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Refresh JWT token.

    Requires valid current token.
    Returns new token with updated expiry.
    """
    try:
        new_token = refresh_token(credentials.credentials)

        # Get user info from current token
        payload = validate_token(credentials.credentials)

        return TokenResponse(
            access_token=new_token,
            token_type="bearer",
            user={
                "id": int(payload["sub"]),
                "email": payload["email"],
                "name": payload["name"],
                "user_image": payload.get("user_image"),
            },
        )

    except Exception as e:
        logger.warning("Token refresh failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Dependency to validate JWT and get current user.

    Returns:
        dict: User info from JWT payload

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        # Validate token
        payload = validate_token(credentials.credentials)

        # Get user from database to check if still enabled
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(int(payload["sub"]))

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.lower() if user.role else "user",  # Ensure role is lowercase
            "sub": payload["sub"],  # Keep for session manager
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Authentication failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
