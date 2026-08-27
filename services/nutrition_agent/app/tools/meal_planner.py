"""Meal planner that generates meal suggestions aligned with macro targets."""
from typing import Any

# Sample meal templates (would be expanded with food database queries)
MEAL_TEMPLATES = {
    "omnivore": {
        "breakfast": [
            {"name": "Scrambled eggs with toast", "calories": 400, "protein_g": 25, "carbs_g": 30, "fat_g": 18},
            {"name": "Oatmeal with berries and almonds", "calories": 350, "protein_g": 12, "carbs_g": 55, "fat_g": 10},
            {"name": "Greek yogurt parfait with granola", "calories": 380, "protein_g": 20, "carbs_g": 45, "fat_g": 12},
        ],
        "lunch": [
            {"name": "Grilled chicken salad with quinoa", "calories": 450, "protein_g": 40, "carbs_g": 35, "fat_g": 15},
            {"name": "Turkey wrap with vegetables", "calories": 420, "protein_g": 35, "carbs_g": 40, "fat_g": 12},
            {"name": "Tuna salad with mixed greens", "calories": 380, "protein_g": 35, "carbs_g": 20, "fat_g": 18},
        ],
        "dinner": [
            {"name": "Salmon with brown rice and broccoli", "calories": 550, "protein_g": 40, "carbs_g": 45, "fat_g": 22},
            {"name": "Chicken stir-fry with vegetables", "calories": 480, "protein_g": 38, "carbs_g": 40, "fat_g": 18},
            {"name": "Lean beef with sweet potato", "calories": 520, "protein_g": 42, "carbs_g": 48, "fat_g": 16},
        ],
        "snack": [
            {"name": "Apple with peanut butter", "calories": 200, "protein_g": 7, "carbs_g": 22, "fat_g": 10},
            {"name": "Greek yogurt", "calories": 120, "protein_g": 15, "carbs_g": 10, "fat_g": 0},
            {"name": "Handful of almonds", "calories": 160, "protein_g": 6, "carbs_g": 6, "fat_g": 14},
        ],
    },
    "vegetarian": {
        "breakfast": [
            {"name": "Vegetable omelet with cheese", "calories": 380, "protein_g": 22, "carbs_g": 15, "fat_g": 24},
            {"name": "Oatmeal with protein powder", "calories": 350, "protein_g": 25, "carbs_g": 50, "fat_g": 8},
        ],
        "lunch": [
            {"name": "Lentil soup with whole grain bread", "calories": 420, "protein_g": 18, "carbs_g": 65, "fat_g": 10},
            {"name": "Caprese salad with quinoa", "calories": 400, "protein_g": 16, "carbs_g": 45, "fat_g": 18},
        ],
        "dinner": [
            {"name": "Tofu stir-fry with brown rice", "calories": 480, "protein_g": 22, "carbs_g": 55, "fat_g": 18},
            {"name": "Vegetable curry with chickpeas", "calories": 450, "protein_g": 18, "carbs_g": 60, "fat_g": 16},
        ],
        "snack": [
            {"name": "Hummus with vegetables", "calories": 180, "protein_g": 6, "carbs_g": 18, "fat_g": 10},
            {"name": "Cottage cheese with fruit", "calories": 150, "protein_g": 14, "carbs_g": 15, "fat_g": 3},
        ],
    },
    "vegan": {
        "breakfast": [
            {"name": "Tofu scramble with vegetables", "calories": 350, "protein_g": 20, "carbs_g": 25, "fat_g": 18},
            {"name": "Oatmeal with almond milk and banana", "calories": 320, "protein_g": 10, "carbs_g": 58, "fat_g": 8},
        ],
        "lunch": [
            {"name": "Buddha bowl with quinoa and chickpeas", "calories": 450, "protein_g": 18, "carbs_g": 65, "fat_g": 14},
            {"name": "Lentil salad with tahini dressing", "calories": 420, "protein_g": 20, "carbs_g": 50, "fat_g": 16},
        ],
        "dinner": [
            {"name": "Tempeh stir-fry with vegetables", "calories": 480, "protein_g": 25, "carbs_g": 45, "fat_g": 20},
            {"name": "Black bean tacos with avocado", "calories": 460, "protein_g": 18, "carbs_g": 55, "fat_g": 18},
        ],
        "snack": [
            {"name": "Mixed nuts", "calories": 170, "protein_g": 6, "carbs_g": 7, "fat_g": 15},
            {"name": "Apple with almond butter", "calories": 190, "protein_g": 5, "carbs_g": 24, "fat_g": 9},
        ],
    },
    "pescatarian": {
        "breakfast": [
            {"name": "Smoked salmon with cream cheese on bagel", "calories": 420, "protein_g": 22, "carbs_g": 35, "fat_g": 20},
            {"name": "Greek yogurt with granola", "calories": 360, "protein_g": 18, "carbs_g": 48, "fat_g": 10},
        ],
        "lunch": [
            {"name": "Tuna salad with mixed greens", "calories": 380, "protein_g": 35, "carbs_g": 20, "fat_g": 18},
            {"name": "Shrimp and vegetable stir-fry", "calories": 350, "protein_g": 30, "carbs_g": 30, "fat_g": 12},
        ],
        "dinner": [
            {"name": "Baked cod with quinoa and vegetables", "calories": 450, "protein_g": 40, "carbs_g": 40, "fat_g": 12},
            {"name": "Salmon with roasted vegetables", "calories": 500, "protein_g": 38, "carbs_g": 25, "fat_g": 26},
        ],
        "snack": [
            {"name": "Sardines on crackers", "calories": 180, "protein_g": 15, "carbs_g": 12, "fat_g": 8},
            {"name": "Greek yogurt", "calories": 120, "protein_g": 15, "carbs_g": 10, "fat_g": 0},
        ],
    },
}


def generate_meal_plan(
    macro_targets: dict,
    dietary_preference: str = "omnivore",
    meals_per_day: int = 3,
    allergies: list[str] = None,
) -> dict:
    """
    Generate a simple meal plan aligned with macro targets.

    Args:
        macro_targets: dict with calories, protein_g, carbs_g, fat_g
        dietary_preference: omnivore, vegetarian, vegan, pescatarian
        meals_per_day: Number of meals (3 = breakfast/lunch/dinner, 4 = +snack)
        allergies: List of allergens to avoid (not yet implemented)

    Returns:
        dict with meals for each meal type and totals
    """
    # Get meal templates for dietary preference
    templates = MEAL_TEMPLATES.get(dietary_preference, MEAL_TEMPLATES["omnivore"])

    # Simple distribution: 30% breakfast, 35% lunch, 35% dinner, 0-10% snacks
    target_calories = macro_targets["calories"]

    meal_plan = {}
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0

    # Breakfast (30%)
    if meals_per_day >= 1:
        breakfast_options = templates.get("breakfast", [])
        if breakfast_options:
            # Pick closest to target
            target_breakfast_cal = target_calories * 0.30
            breakfast = min(breakfast_options, key=lambda x: abs(x["calories"] - target_breakfast_cal))
            meal_plan["breakfast"] = breakfast
            total_calories += breakfast["calories"]
            total_protein += breakfast["protein_g"]
            total_carbs += breakfast["carbs_g"]
            total_fat += breakfast["fat_g"]

    # Lunch (35%)
    if meals_per_day >= 2:
        lunch_options = templates.get("lunch", [])
        if lunch_options:
            target_lunch_cal = target_calories * 0.35
            lunch = min(lunch_options, key=lambda x: abs(x["calories"] - target_lunch_cal))
            meal_plan["lunch"] = lunch
            total_calories += lunch["calories"]
            total_protein += lunch["protein_g"]
            total_carbs += lunch["carbs_g"]
            total_fat += lunch["fat_g"]

    # Dinner (35%)
    if meals_per_day >= 3:
        dinner_options = templates.get("dinner", [])
        if dinner_options:
            target_dinner_cal = target_calories * 0.35
            dinner = min(dinner_options, key=lambda x: abs(x["calories"] - target_dinner_cal))
            meal_plan["dinner"] = dinner
            total_calories += dinner["calories"]
            total_protein += dinner["protein_g"]
            total_carbs += dinner["carbs_g"]
            total_fat += dinner["fat_g"]

    # Snacks (if 4+ meals)
    if meals_per_day >= 4:
        snack_options = templates.get("snack", [])
        if snack_options:
            target_snack_cal = target_calories * 0.10
            snack = min(snack_options, key=lambda x: abs(x["calories"] - target_snack_cal))
            meal_plan["snack"] = snack
            total_calories += snack["calories"]
            total_protein += snack["protein_g"]
            total_carbs += snack["carbs_g"]
            total_fat += snack["fat_g"]

    return {
        "meals": meal_plan,
        "total_calories": total_calories,
        "total_protein_g": round(total_protein, 1),
        "total_carbs_g": round(total_carbs, 1),
        "total_fat_g": round(total_fat, 1),
        "target_calories": target_calories,
        "variance_calories": total_calories - target_calories,
    }
