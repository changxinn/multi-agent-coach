"""
Database seeding script.

Creates default admin user with properly hashed password.
Safe to run multiple times (idempotent).
"""
import asyncio
import logging
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt

from app.config import get_settings
from app.db.database import AsyncSessionLocal, run_migrations
from app.db.models import User, UserFitnessProfile

logger = logging.getLogger(__name__)
settings = get_settings()


async def seed_admin_user(session: AsyncSession) -> None:
    """
    Create admin user if not exists.

    Uses bcrypt to hash password from environment variables.
    """
    # Check if admin already exists
    result = await session.execute(
        select(User).where(User.email == settings.SEED_ADMIN_EMAIL)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.info("Admin user already exists: %s", settings.SEED_ADMIN_EMAIL)
        return

    # Hash password with bcrypt
    password_hash = bcrypt.hashpw(
        settings.SEED_ADMIN_PASSWORD.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    # Create admin user
    admin_user = User(
        email=settings.SEED_ADMIN_EMAIL,
        password=password_hash,
        name=settings.SEED_ADMIN_NAME,
        role="ADMIN",
        enabled=True,
    )

    session.add(admin_user)
    await session.flush()  # Get the ID

    # Create fitness profile
    fitness_profile = UserFitnessProfile(
        user_id=admin_user.id,
        fitness_goal="general fitness",
        fitness_level="beginner",
    )

    session.add(fitness_profile)
    await session.commit()

    logger.info("Admin user created successfully: %s", settings.SEED_ADMIN_EMAIL)


async def seed_database() -> None:
    """
    Main seeding function.

    Runs migrations first, then seeds data.
    """
    logger.info("Starting database seeding...")

    # Run migrations first
    await run_migrations()

    # Seed admin user
    async with AsyncSessionLocal() as session:
        try:
            await seed_admin_user(session)
            logger.info("Database seeding completed successfully")
        except Exception as e:
            await session.rollback()
            logger.error("Database seeding failed: %s", e)
            raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(seed_database())
