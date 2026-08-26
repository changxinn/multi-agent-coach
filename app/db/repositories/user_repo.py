"""
User repository for database operations.

Provides methods for user CRUD operations.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import User, UserFitnessProfile


class UserRepository:
    """Repository for user database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User email

        Returns:
            User or None if not found
        """
        result = await self.db.execute(
            select(User)
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None if not found
        """
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password: str,
        name: str,
        role: str = "USER",
    ) -> User:
        """
        Create a new user.

        Args:
            email: User email
            password: Password (should be pre-hashed with bcrypt)
            name: User name
            role: User role (USER, STAFF, ADMIN)

        Returns:
            Created user
        """
        user = User(
            email=email,
            password=password,
            name=name,
            role=role,
            enabled=True,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        # Create fitness profile
        fitness_profile = UserFitnessProfile(user_id=user.id)
        self.db.add(fitness_profile)
        await self.db.flush()

        return user

    async def update_role(self, user_id: int, role: str) -> Optional[User]:
        """
        Update user role.

        Args:
            user_id: User ID
            role: New role

        Returns:
            Updated user or None if not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None

        user.role = role
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def update_fitness_profile(
        self,
        user_id: int,
        fitness_goal: Optional[str] = None,
        fitness_level: Optional[str] = None,
        weight_kg: Optional[float] = None,
        height_cm: Optional[float] = None,
        age: Optional[int] = None,
    ) -> Optional[UserFitnessProfile]:
        """
        Update user fitness profile.

        Args:
            user_id: User ID
            fitness_goal: Fitness goal
            fitness_level: Fitness level
            weight_kg: Weight in kg
            height_cm: Height in cm
            age: Age in years

        Returns:
            Updated fitness profile or None if user not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None

        if not user.fitness_profile:
            # Create profile if doesn't exist
            user.fitness_profile = UserFitnessProfile(user_id=user_id)

        profile = user.fitness_profile

        if fitness_goal is not None:
            profile.fitness_goal = fitness_goal
        if fitness_level is not None:
            profile.fitness_level = fitness_level
        if weight_kg is not None:
            profile.weight_kg = weight_kg
        if height_cm is not None:
            profile.height_cm = height_cm
        if age is not None:
            profile.age = age

        await self.db.flush()
        await self.db.refresh(profile)

        return profile

    async def delete_user(self, user_id: int) -> bool:
        """
        Delete user by ID.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False

        await self.db.delete(user)
        await self.db.flush()

        return True
