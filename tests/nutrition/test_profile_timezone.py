"""Nutrition profile timezone validation and persistence coverage."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from services.nutrition_agent.app.repository import NutritionRepository
from services.nutrition_agent.app.schemas import NutritionProfileUpsert


class _Settings:
    @staticmethod
    def validated_schema() -> str: return "systemdb"
def test_profile_accepts_a_valid_iana_timezone() -> None:
    assert NutritionProfileUpsert(timezone=" America/New_York ").timezone == "America/New_York"
    assert NutritionProfileUpsert(timezone="Asia/Singapore").timezone == "Asia/Singapore"
@pytest.mark.parametrize("timezone", ["", "Not/A_Timezone", "UTC+01:00"])
def test_profile_rejects_invalid_iana_timezones(timezone: str) -> None:
    with pytest.raises(ValidationError):
        NutritionProfileUpsert(timezone=timezone)
@pytest.mark.asyncio
async def test_profile_upsert_persists_timezone_and_returns_it() -> None:
    class Pool:
        query = ""; arguments: tuple[object, ...] = ()
        async def fetchrow(self, query: str, *arguments: object) -> dict[str, object]:
            self.query, self.arguments = query, arguments
            return {"user_id": arguments[0], "timezone": arguments[1], "dietary_preference": arguments[2], "dietary_restrictions": [], "allergies": [], "meals_per_day": 3, "activity_level": "moderate", "age": None, "gender": None, "weight_kg": None, "height_cm": None, "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC)}
    repository = NutritionRepository(_Settings()); pool = Pool(); repository.pool = pool  # type: ignore[assignment]
    profile = await repository.upsert_profile(42, NutritionProfileUpsert(timezone="Asia/Singapore"))
    assert "timezone" in pool.query and pool.arguments[1] == "Asia/Singapore" and profile.timezone == "Asia/Singapore"


@pytest.mark.asyncio
async def test_profile_upsert_handles_json_strings_and_ignores_legacy_columns() -> None:
    class Pool:
        async def fetchrow(self, _query: str, *arguments: object) -> dict[str, object]:
            return {
                "user_id": arguments[0], "timezone": arguments[1], "dietary_preference": arguments[2],
                "dietary_restrictions": "[]", "allergies": "[]", "meals_per_day": 3,
                "activity_level": "moderate", "age": None, "gender": None, "weight_kg": None,
                "height_cm": None, "target_calories": None, "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }

    repository = NutritionRepository(_Settings()); repository.pool = Pool()  # type: ignore[assignment]
    profile = await repository.upsert_profile(42, NutritionProfileUpsert(timezone="Asia/Singapore"))

    assert profile.dietary_restrictions == []
    assert profile.allergies == []