"""Pure, decimal-safe target calculations for nutrition coaching."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ACTIVITY_MULTIPLIERS = {
    "sedentary": Decimal("1.2"),
    "light": Decimal("1.375"),
    "moderate": Decimal("1.55"),
    "very_active": Decimal("1.725"),
    "extra_active": Decimal("1.9"),
}
GOAL_CALORIE_MULTIPLIERS = {
    "maintenance": Decimal(1),
    "fat_loss": Decimal("0.85"),
    "muscle_gain": Decimal("1.10"),
    "performance": Decimal("1.05"),
}
GOAL_PROTEIN_PER_KG = {
    "maintenance": Decimal("1.6"),
    "fat_loss": Decimal("1.8"),
    "muscle_gain": Decimal("1.8"),
    "performance": Decimal("1.7"),
}


@dataclass(frozen=True)
class NutritionTargets:
    bmr_kcal: int
    tdee_kcal: int
    calorie_target_kcal: int
    protein_target_g: Decimal
    carbohydrate_target_g: Decimal
    fat_target_g: Decimal
    fiber_target_g: Decimal
    calculation_method: str = "mifflin_st_jeor_v1"


def calculate_targets(
    *,
    sex: str,
    age: int,
    weight_kg: Decimal,
    height_cm: Decimal,
    activity_level: str,
    goal: str,
) -> NutritionTargets:
    """Calculate Mifflin-St Jeor energy and macro targets for a valid profile."""
    if (
        sex not in {"female", "male"}
        or activity_level not in ACTIVITY_MULTIPLIERS
        or goal not in GOAL_CALORIE_MULTIPLIERS
    ):
        raise ValueError("Unsupported nutrition profile value")
    if age <= 0 or weight_kg <= 0 or height_cm <= 0:
        raise ValueError("Age, weight_kg, and height_cm must be positive")

    bmr = (
        Decimal(10) * weight_kg
        + Decimal("6.25") * height_cm
        - Decimal(5) * age
        + (Decimal(5) if sex == "male" else Decimal(-161))
    )
    tdee = bmr * ACTIVITY_MULTIPLIERS[activity_level]
    calories = tdee * GOAL_CALORIE_MULTIPLIERS[goal]
    protein = weight_kg * GOAL_PROTEIN_PER_KG[goal]
    fat = weight_kg * Decimal("0.8")
    carbohydrates = max(Decimal(0), (calories - protein * 4 - fat * 9) / 4)

    def whole(value: Decimal) -> int:
        return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    def grams(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return NutritionTargets(
        bmr_kcal=whole(bmr),
        tdee_kcal=whole(tdee),
        calorie_target_kcal=whole(calories),
        protein_target_g=grams(protein),
        carbohydrate_target_g=grams(carbohydrates),
        fat_target_g=grams(fat),
        fiber_target_g=grams(Decimal(14) * calories / Decimal(1000)),
    )
