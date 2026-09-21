from decimal import Decimal

import pytest

from app.services.nutrition_calculator import calculate_targets


def test_mifflin_st_jeor_maintenance_targets_are_deterministic():
    targets = calculate_targets(
        sex="male",
        age=30,
        weight_kg=Decimal(80),
        height_cm=Decimal(180),
        activity_level="moderate",
        goal="maintenance",
    )

    assert targets.bmr_kcal == 1780
    assert targets.tdee_kcal == 2759
    assert targets.calorie_target_kcal == 2759
    assert targets.protein_target_g == Decimal("128.00")
    assert targets.fiber_target_g == Decimal("38.63")


def test_fat_loss_policy_reduces_calories_and_raises_protein():
    maintenance = calculate_targets(
        sex="female",
        age=28,
        weight_kg=Decimal(65),
        height_cm=Decimal(165),
        activity_level="light",
        goal="maintenance",
    )
    fat_loss = calculate_targets(
        sex="female",
        age=28,
        weight_kg=Decimal(65),
        height_cm=Decimal(165),
        activity_level="light",
        goal="fat_loss",
    )

    assert fat_loss.calorie_target_kcal < maintenance.calorie_target_kcal
    assert fat_loss.protein_target_g > maintenance.protein_target_g


@pytest.mark.parametrize(
    "sex, activity_level, goal",
    [
        ("other", "light", "maintenance"),
        ("male", "invalid", "maintenance"),
        ("male", "light", "invalid"),
    ],
)
def test_invalid_profile_values_are_rejected(sex, activity_level, goal):
    with pytest.raises(ValueError, match="Unsupported nutrition profile value"):
        calculate_targets(
            sex=sex,
            age=30,
            weight_kg=Decimal(80),
            height_cm=Decimal(180),
            activity_level=activity_level,
            goal=goal,
        )


@pytest.mark.parametrize(
    "age, weight_kg, height_cm",
    [
        (0, Decimal(80), Decimal(180)),
        (-1, Decimal(80), Decimal(180)),
        (30, Decimal(0), Decimal(180)),
        (30, Decimal("-0.1"), Decimal(180)),
        (30, Decimal(80), Decimal(0)),
        (30, Decimal(80), Decimal("-0.1")),
    ],
)
def test_nonpositive_measurements_are_rejected(age, weight_kg, height_cm):
    with pytest.raises(
        ValueError,
        match="Age, weight_kg, and height_cm must be positive",
    ):
        calculate_targets(
            sex="male",
            age=age,
            weight_kg=weight_kg,
            height_cm=height_cm,
            activity_level="moderate",
            goal="maintenance",
        )
