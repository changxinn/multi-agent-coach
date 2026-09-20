"""
User profile service for fetching fitness profiles from database.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserFitnessProfile
from app.db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service for user profile operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def get_user_profile(self, user_id: int) -> dict[str, Any]:
        """
        Get user profile for LangGraph state.

        Args:
            user_id: User ID

        Returns:
            Dict with user profile data for agents

        Raises:
            ValueError: If user not found
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Fetch fitness profile separately (relationship removed)
        from sqlalchemy import select

        result = await self.db.execute(
            select(UserFitnessProfile).where(UserFitnessProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        return {
            "user_id": user.id,
            "name": user.name,
            "fitness_goal": profile.fitness_goal if profile else "general fitness",
            "fitness_level": profile.fitness_level if profile else "beginner",
            "weight_kg": float(profile.weight_kg)
            if profile and profile.weight_kg
            else None,
            "height_cm": float(profile.height_cm)
            if profile and profile.height_cm
            else None,
            "age": profile.age if profile else None,
        }

    async def update_fitness_profile(
        self,
        user_id: int,
        fitness_goal: str | None = None,
        fitness_level: str | None = None,
        weight_kg: float | None = None,
        height_cm: float | None = None,
        age: int | None = None,
    ) -> dict[str, Any]:
        """
        Update user fitness profile.

        Args:
            user_id: User ID
            fitness_goal: New fitness goal
            fitness_level: New fitness level
            weight_kg: New weight in kg
            height_cm: New height in cm
            age: New age

        Returns:
            Updated profile dict

        Raises:
            ValueError: If user not found
        """
        profile = await self.user_repo.update_fitness_profile(
            user_id=user_id,
            fitness_goal=fitness_goal,
            fitness_level=fitness_level,
            weight_kg=weight_kg,
            height_cm=height_cm,
            age=age,
        )

        if not profile:
            raise ValueError(f"User {user_id} not found")

        return {
            "user_id": user_id,
            "fitness_goal": profile.fitness_goal,
            "fitness_level": profile.fitness_level,
            "weight_kg": float(profile.weight_kg) if profile.weight_kg else None,
            "height_cm": float(profile.height_cm) if profile.height_cm else None,
            "age": profile.age,
        }

    async def get_complete_user_data(self, user_id: int) -> dict[str, Any]:
        """
        Get complete user data (auth + profile).

        Args:
            user_id: User ID

        Returns:
            Dict with all user data

        Raises:
            ValueError: If user not found
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise ValueError(f"User {user_id} not found")

        profile = user.fitness_profile

        return {
            # Auth data
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            # Profile data
            "fitness_goal": profile.fitness_goal if profile else "general fitness",
            "fitness_level": profile.fitness_level if profile else "beginner",
            "weight_kg": float(profile.weight_kg)
            if profile and profile.weight_kg
            else None,
            "height_cm": float(profile.height_cm)
            if profile and profile.height_cm
            else None,
            "age": profile.age if profile else None,
        }
