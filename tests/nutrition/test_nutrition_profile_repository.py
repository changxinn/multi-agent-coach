import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.nutrition_repo import NutritionRepository


@pytest.mark.asyncio
async def test_upsert_profile_persists_dietary_preferences_and_restrictions():
    db = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.one.return_value = {"user_id": 7}
    db.execute.return_value = result

    await NutritionRepository(db).upsert_profile(
        7,
        {
            "sex_for_energy_equation": "female",
            "activity_level": "moderate",
            "nutrition_goal": "maintenance",
            "dietary_preferences": ["plant based", "spicy food"],
            "dietary_restrictions": ["gluten free"],
            "allergies": ["milk"],
        },
    )

    parameters = db.execute.await_args.args[1]
    assert json.loads(parameters["dietary_preferences"]) == [
        "plant based",
        "spicy food",
    ]
    assert json.loads(parameters["dietary_restrictions"]) == ["gluten free"]
    assert json.loads(parameters["allergies"]) == ["milk"]
