from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

engine = None
SessionLocal = None


def session_factory():
    global engine, SessionLocal
    if SessionLocal is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("TRAINING_DATABASE_URL is required for Training Agent")
        url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, pool_pre_ping=True)
        SessionLocal = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    from .migrations import run_migrations

    session_factory()
    await run_migrations(engine)


async def close_db() -> None:
    if engine is not None:
        await engine.dispose()
