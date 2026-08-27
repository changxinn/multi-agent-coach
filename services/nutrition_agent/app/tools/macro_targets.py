"""Macro target calculator based on fitness goals."""

# Safety thresholds per clinical guidelines
MIN_CALORIES_WOMEN = 1200
MIN_CALORIES_MEN = 1500
MAX_SAFE_WEIGHT_LOSS_PER_WEEK = 1.0  # kg
CALORIES_PER_KG_FAT = 7700


def calculate_macro_targets(
    tdee: int,
    weight_kg: float,
    fitness_goal: str,
    gender: str = "other",
) -> dict:
    """
    Calculate macronutrient targets based on fitness goals.

    Evidence-based ratios:
    - Weight loss: TDEE - 500 kcal, protein 2.0g/kg, fat 0.8g/kg, rest carbs
    - Maintenance: TDEE, protein 1.6g/kg, fat 1.0g/kg, rest carbs
    - Muscle gain: TDEE + 250 kcal, protein 2.2g/kg, fat 1.0g/kg, rest carbs

    Safety checks:
    - Minimum calories: 1200 (women), 1500 (men)
    - Maximum weight loss: 1 kg/week (~1000 kcal deficit)

    Args:
        tdee: Total Daily Energy Expenditure in calories
        weight_kg: Body weight in kilograms
        fitness_goal: One of: weight_loss, maintenance, muscle_gain
        gender: 'male', 'female', or 'other'

    Returns:
        dict with calories, protein_g, carbs_g, fat_g, and percentages
    """
    fitness_goal = fitness_goal.lower()

    # Calculate target calories based on goal
    if fitness_goal == "weight_loss":
        # 500 kcal deficit = ~0.5 kg/week loss
        target_calories = tdee - 500
        protein_per_kg = 2.0  # Higher protein preserves muscle during deficit
        fat_per_kg = 0.8
    elif fitness_goal == "muscle_gain":
        # 250 kcal surplus = lean bulk
        target_calories = tdee + 250
        protein_per_kg = 2.2  # Higher protein for muscle synthesis
        fat_per_kg = 1.0
    else:  # maintenance
        target_calories = tdee
        protein_per_kg = 1.6
        fat_per_kg = 1.0

    # Safety check: minimum calories
    min_calories = MIN_CALORIES_WOMEN if gender.lower() == "female" else MIN_CALORIES_MEN
    if target_calories < min_calories:
        target_calories = min_calories

    # Calculate macros
    protein_g = protein_per_kg * weight_kg
    fat_g = fat_per_kg * weight_kg

    # Carbs = remaining calories after protein and fat
    # Protein: 4 cal/g, Fat: 9 cal/g, Carbs: 4 cal/g
    protein_calories = protein_g * 4
    fat_calories = fat_g * 9
    remaining_calories = target_calories - protein_calories - fat_calories

    # Ensure carbs don't go negative
    if remaining_calories < 0:
        # Adjust fat down first, then protein
        fat_g = max(0.5 * weight_kg, fat_g + remaining_calories / 9)
        remaining_calories = target_calories - (protein_g * 4) - (fat_g * 9)

    carbs_g = remaining_calories / 4

    # Calculate percentages
    total_macro_calories = (protein_g * 4) + (carbs_g * 4) + (fat_g * 9)
    protein_percentage = round((protein_g * 4) / total_macro_calories * 100, 1)
    carbs_percentage = round((carbs_g * 4) / total_macro_calories * 100, 1)
    fat_percentage = round((fat_g * 9) / total_macro_calories * 100, 1)

    return {
        "calories": round(target_calories),
        "protein_g": round(protein_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_g": round(fat_g, 1),
        "protein_percentage": protein_percentage,
        "carbs_percentage": carbs_percentage,
        "fat_percentage": fat_percentage,
    }
