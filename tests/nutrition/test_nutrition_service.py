from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.services.nutrition_service import NutritionService


@pytest.mark.asyncio
async def test_adherence_includes_the_date_for_each_daily_summary():
    service = NutritionService(AsyncMock())
    service.get_daily_summary = AsyncMock(
        side_effect=[{"calories": 100}, {"calories": 200}]
    )

    result = await service.get_adherence(7, date(2026, 9, 20), date(2026, 9, 21))

    assert result == [
        {"calories": 100, "summary_date": date(2026, 9, 20)},
        {"calories": 200, "summary_date": date(2026, 9, 21)},
    ]
    service.get_daily_summary.assert_has_awaits(
        [
            ((7, date(2026, 9, 20)),),
            ((7, date(2026, 9, 21)),),
        ]
    )


@pytest.mark.asyncio
async def test_apply_targets_updates_same_day_snapshot_in_place():
    repo = AsyncMock()
    repo.get_profile_with_measurements.return_value = {
        "sex_for_energy_equation": "male",
        "activity_level": "moderate",
        "nutrition_goal": "maintenance",
        "age": 30,
        "weight_kg": Decimal(80),
        "height_cm": Decimal(180),
    }
    repo.lock_open_target.return_value = {
        "id": 42,
        "effective_from": datetime.now(UTC).date(),
    }
    repo.update_target.return_value = {
        "id": 42,
        "effective_from": datetime.now(UTC).date(),
    }

    with patch("app.services.nutrition_service.NutritionRepository", return_value=repo):
        result = await NutritionService(AsyncMock()).calculate_targets(
            7, confirm_apply=True
        )

    assert result == {
        "id": 42,
        "effective_from": datetime.now(UTC).date(),
        "applied": True,
    }
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
        "weight_kg": Decimal(60),
        "height_cm": Decimal(165),
    }
    repo.lock_open_target.return_value = {"id": 11, "effective_from": date(2026, 1, 1)}
    repo.create_target.return_value = {
        "id": 12,
        "effective_from": datetime.now(UTC).date(),
    }

    with patch("app.services.nutrition_service.NutritionRepository", return_value=repo):
        result = await NutritionService(AsyncMock()).calculate_targets(
            7, confirm_apply=True
        )

    assert result["applied"] is True
    repo.close_target.assert_awaited_once_with(
        11, datetime.now(UTC).date() - timedelta(days=1)
    )
    repo.create_target.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_summary_calculates_adherence_and_remaining_macros():
    repo = AsyncMock()
    repo.get_daily_totals.return_value = {
        "meal_count": 2,
        "calories": Decimal(1800),
        "protein_g": Decimal(100),
        "carbohydrate_g": Decimal(200),
        "fat_g": Decimal(50),
        "fiber_g": Decimal(20),
    }
    client = AsyncMock()
    client.get_nutrition_context.return_value = {
        "target_snapshot": {
            "id": 3,
            "calorie_target_kcal": 2000,
            "protein_target_g": Decimal(125),
            "carbohydrate_target_g": Decimal(225),
            "fat_target_g": Decimal(60),
        }
    }
    with patch("app.services.nutrition_service.NutritionRepository", return_value=repo):
        result = await NutritionService(
            AsyncMock(), nutrition_client=client
        ).get_daily_summary(7, datetime.now(UTC).date())
    assert result["calorie_adherence_pct"] == Decimal("90.00")
    assert result["remaining"]["protein_g"] == Decimal(25)
    repo.get_target_for_date.assert_not_called()
    repo.upsert_daily_summary.assert_not_called()
    client.get_nutrition_context.assert_awaited_once_with(7, datetime.now(UTC).date())
