"""Unit coverage for migration-owned Nutrition repository foundations."""

from __future__ import annotations

import pytest

from services.nutrition_agent.app.repository import NutritionRepository


class _NutritionSettings:
    DATABASE_URL = "postgresql://user:password@localhost:5432/systemdb"

    @staticmethod
    def validated_schema() -> str:
        return "systemdb"


class _ValidationConnection:
    def __init__(self, versions: list[str], tables: set[str]) -> None:
        self.versions = versions
        self.tables = tables
        self.executed: list[str] = []

    async def fetch(self, query: str) -> list[dict[str, str]]:
        self.executed.append(query)
        return [{"version": version} for version in self.versions]

    async def fetchval(self, query: str, table: str) -> bool:
        self.executed.append(query)
        return table in self.tables


class _Acquire:
    def __init__(self, connection: _ValidationConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _ValidationConnection:
        return self.connection

    async def __aexit__(self, *_: object) -> None:
        return None


class _Pool:
    def __init__(self, connection: _ValidationConnection) -> None:
        self.connection = connection

    def acquire(self) -> _Acquire:
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_schema_validation_is_read_only_when_required_schema_exists() -> None:
    tables = {
        "systemdb.users",
        "systemdb.nutrition_profiles",
        "systemdb.meal_logs",
        "systemdb.nutrition_assessments",
        "systemdb.food_cache",
        "systemdb.nutrition_targets",
    }
    connection = _ValidationConnection(["000", "006", "007", "008", "009", "010"], tables)
    repository = NutritionRepository(_NutritionSettings())
    repository.pool = _Pool(connection)  # type: ignore[assignment]

    await repository.validate_schema()

    assert all("CREATE" not in query.upper() for query in connection.executed)
    assert all("ALTER" not in query.upper() for query in connection.executed)


@pytest.mark.asyncio
async def test_schema_validation_requires_migration_010() -> None:
    repository = NutritionRepository(_NutritionSettings())
    repository.pool = _Pool(_ValidationConnection(["000", "005"], set()))  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="010 is not applied"):
        await repository.validate_schema()
