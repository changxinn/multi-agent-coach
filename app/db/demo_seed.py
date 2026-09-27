"""Opt-in local demo-user seeding."""

import logging
from dataclasses import dataclass

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

DEMO_PASSWORD = "DemoPass123!"


@dataclass(frozen=True)
class DemoUser:
    """A local demo account and its initial fitness profile."""

    email: str
    name: str
    fitness_goal: str
    fitness_level: str
    weight_kg: float
    height_cm: float
    age: int


DEMO_USERS = (
    DemoUser(
        email="alex.demo@example.com",
        name="Alex Demo",
        fitness_goal="build strength",
        fitness_level="intermediate",
        weight_kg=78.0,
        height_cm=180.0,
        age=31,
    ),
    DemoUser(
        email="sam.demo@example.com",
        name="Sam Demo",
        fitness_goal="improve endurance",
        fitness_level="beginner",
        weight_kg=62.0,
        height_cm=168.0,
        age=27,
    ),
)


async def seed_demo_users(db: AsyncSession, settings: Settings) -> None:
    """Create local demo users once, without changing existing user data."""
    if not settings.SEED_DEMO_USERS:
        return

    user_repo = UserRepository(db)
    created_emails: list[str] = []

    try:
        for demo_user in DEMO_USERS:
            if await user_repo.get_by_email(demo_user.email):
                continue

            password_hash = bcrypt.hashpw(
                DEMO_PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=12)
            ).decode("utf-8")
            user = await user_repo.create_user(
                email=demo_user.email,
                password=password_hash,
                name=demo_user.name,
            )
            await user_repo.update_fitness_profile(
                user_id=user.id,
                fitness_goal=demo_user.fitness_goal,
                fitness_level=demo_user.fitness_level,
                weight_kg=demo_user.weight_kg,
                height_cm=demo_user.height_cm,
                age=demo_user.age,
            )
            created_emails.append(demo_user.email)

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    if created_emails:
        logger.info("Created local demo users: %s", ", ".join(created_emails))
    else:
        logger.info("Local demo users already exist; no seed changes applied")
