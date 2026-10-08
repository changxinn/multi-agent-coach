"""
Authentication routes: login, register, token refresh.
"""

import logging

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import (
    CurrentUserProfileResponse,
    FitnessProfileUpdateRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.db.database import get_db
from app.db.repositories.user_repo import UserRepository
from app.services.jwt_service import create_access_token, refresh_token, validate_token
from app.services.training_agent_client import (
    TrainingAgentClient,
    TrainingAgentUnavailableError,
)
from app.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


def get_training_agent() -> TrainingAgentClient:
    return TrainingAgentClient()


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
    if not bcrypt.checkpw(
        request.password.encode("utf-8"), user.password.encode("utf-8")
    ):
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

    token = create_access_token(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "user_image": None,
        }
    )

    logger.info("User logged in successfully: %s", user.email)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "user_image": None,
        },
    )


@router.post("/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.

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
    )

    logger.info("New user registered: %s (ID: %d)", user.email, user.id)

    token = create_access_token(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "user_image": None,
        }
    )

    logger.info("New user registered: %s (ID: %d)", user.email, user.id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "user_image": None,
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


@router.get("/auth/profile", response_model=CurrentUserProfileResponse)
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    training_agent: TrainingAgentClient = Depends(get_training_agent),
):
    """Compose global measurements with Training Agent-owned goal and level."""
    profile = await UserProfileService(db).get_user_profile(current_user["id"])
    try:
        training_profile = await training_agent.profile(current_user["id"])
    except TrainingAgentUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    profile.update(
        fitness_goal=training_profile["fitness_goal"],
        fitness_level=training_profile["fitness_level"],
    )
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "fitness_profile": profile,
    }


@router.put("/auth/profile", response_model=CurrentUserProfileResponse)
async def update_profile(
    request: FitnessProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    training_agent: TrainingAgentClient = Depends(get_training_agent),
):
    """Update global measurements locally and training goal/level in Training Agent."""
    values = request.model_dump(exclude_unset=True)
    training_values = {
        key: values.pop(key)
        for key in ("fitness_goal", "fitness_level")
        if key in values
    }
    profile = await UserProfileService(db).update_fitness_profile(
        current_user["id"], **values
    )
    try:
        training_profile = (
            await training_agent.update_profile(current_user["id"], training_values)
            if training_values
            else await training_agent.profile(current_user["id"])
        )
    except TrainingAgentUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    profile.update(
        fitness_goal=training_profile["fitness_goal"],
        fitness_level=training_profile["fitness_level"],
    )
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "fitness_profile": profile,
    }
