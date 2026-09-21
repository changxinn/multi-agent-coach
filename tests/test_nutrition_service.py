from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.services.nutrition_service import NutritionService


@pytest.mark.asyncio
async def test_apply_targets_updates_same_day_snapshot_in_place():
    repo = AsyncMock()
    repo.get_profile_with_measurements.return_value = {
        "sex_for_energy_equation": "male",
        "activity_level": "moderate",
        "nutrition_goal": "maintenance",
        "age": 30,
        "weight_kg": Decimal("80"),
        "height_cm": Decimal("180"),
    }
    repo.lock_open_target.return_value = {"id": 42, "effective_from": date.today()}
    repo.update_target.return_value = {"id": 42, "effective_from": date.today()}

    with patch("app.services.nutrition_service.NutritionRepository", return_value=repo):
        result = await NutritionService(AsyncMock()).calculate_targets(
            7, confirm_apply=True
        )

    assert result == {"id": 42, "effective_from": date.today(), "applied": True}
    repo.update_target.assert_awaited_once()
    repo.close_target.assert_not_awaited()
    repo.create_target.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_targets_closes_previous_snapshot_before_creating_next():
    repo = AsyncMock()
    repo.get_profile_with_measurements.return_value = {
        "sex_for_energy_equation": "female",
        "activity_level": "light",
        "nutrition_goal": "fat_loss",
        "age": 30,
        "weight_kg": Decimal("60"),
        "height_cm": Decimal("165"),
    }
    repo.lock_open_target.return_value = {"id": 11, "effective_from": date(2026, 1, 1)}
    repo.create_target.return_value = {"id": 12, "effective_from": date.today()}

    with patch("app.services.nutrition_service.NutritionRepository", return_value=repo):
        result = await NutritionService(AsyncMock()).calculate_targets(
            7, confirm_apply=True
        )

    assert result["applied"] is True
    repo.close_target.assert_awaited_once_with(11, date.today() - timedelta(days=1))
    repo.create_target.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_summary_calculates_adherence_and_remaining_macros():
    repo = AsyncMock()
    repo.get_daily_totals.return_value = {
        "meal_count": 2, "calories": Decimal("1800"), "protein_g": Decimal("100"),
        "carbohydrate_g": Decimal("200"), "fat_g": Decimal("50"), "fiber_g": Decimal("20"),
    }
    repo.get_target_for_date.return_value = {
        "id": 3, "calorie_target_kcal": 2000, "protein_target_g": Decimal("125"),
        "carbohydrate_target_g": Decimal("225"), "fat_target_g": Decimal("60"),
    }
    repo.upsert_daily_summary.side_effect = lambda _, __, values: values
    with patch("app.services.nutrition_service.NutritionRepository", return_value=repo):
        result = await NutritionService(AsyncMock()).get_daily_summary(7, date.today())
    assert result["calorie_adherence_pct"] == Decimal("90.00")
    assert result["remaining"]["protein_g"] == Decimal("25")
