"""Database ownership and session lifecycle for the Nutrition Agent."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings

engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _session_factory() -> async_sessionmaker[AsyncSession]:
    global engine, SessionLocal
    if SessionLocal is None:
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is required for the Nutrition Agent service"
            )
        database_url = settings.DATABASE_URL.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
        engine = create_async_engine(database_url, pool_pre_ping=True)
        SessionLocal = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    if engine is not None:
        await engine.dispose()
