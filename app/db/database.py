"""
Async database connection and session management.

Uses asyncpg driver for PostgreSQL with connection pooling.
Automatically runs migrations on startup.
"""
import logging
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Create async engine with connection pooling
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for database session.

    Yields:
        AsyncSession: Database session

    Usage:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def run_migrations() -> None:
    """
    Run all migration scripts in order.

    Migrations are idempotent (safe to run multiple times).
    Scripts are executed from app/db/migrations/ directory.
    
    Note: asyncpg requires individual statements, so we split by semicolons.
    """
    migrations_dir = Path(__file__).parent / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        logger.warning("No migration files found in %s", migrations_dir)
        return

    logger.info("Running %d database migrations...", len(migration_files))

    async with engine.begin() as conn:
        for migration_file in migration_files:
            logger.info("Executing migration: %s", migration_file.name)
            sql_content = migration_file.read_text(encoding="utf-8")
            
            # Split SQL into individual statements (asyncpg doesn't support multiple statements)
            # Remove comments and split by semicolons
            statements = []
            for line in sql_content.split('\n'):
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('--'):
                    continue
                statements.append(line)
            
            # Join and split by semicolons, filtering out empty statements
            full_sql = ' '.join(statements)
            individual_statements = [
                stmt.strip() 
                for stmt in full_sql.split(';') 
                if stmt.strip()
            ]
            
            # Execute each statement separately
            for stmt in individual_statements:
                if stmt and not stmt.startswith('--'):
                    try:
                        await conn.execute(text(stmt))
                    except Exception as e:
                        # Ignore errors for IF NOT EXISTS statements
                        if 'already exists' not in str(e).lower():
                            raise

    logger.info("Database migrations completed successfully")


async def init_db() -> None:
    """
    Initialize database connection, run migrations, and seed admin user.

    Call this on application startup.
    """
    try:
        # First, setup database (create DB, schema, tables)
        from app.db.setup import setup_database
        logger.info("Setting up database...")
        
        if not setup_database(settings.DATABASE_URL, settings.DATABASE_SCHEMA):
            logger.warning("Database setup had issues, continuing with migrations...")
        
        # Test connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established")

        # Run migrations
        await run_migrations()

        # Seed admin user (idempotent - only creates if not exists)
        from app.db.seed import seed_admin_user
        async with AsyncSessionLocal() as session:
            await seed_admin_user(session)
            logger.info("Admin user seeding completed")

    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        raise


async def close_db() -> None:
    """
    Close database connections.

    Call this on application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")
