from pathlib import Path


async def run_migrations(engine) -> None:
    migration_dir = Path(__file__).parent / "db" / "migrations"
    async with engine.begin() as connection:
        for migration in sorted(migration_dir.glob("*.sql")):
            for statement in migration.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    await connection.exec_driver_sql(statement)
