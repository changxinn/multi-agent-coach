"""Meal planner that generates meal suggestions aligned with macro targets."""

# Sample meal templates (would be expanded with food database queries)
MEAL_TEMPLATES = {
    "omnivore": {
        "breakfast": [
            {"name": "Scrambled eggs with toast", "calories": 400, "protein_g": 25, "carbs_g": 30, "fat_g": 18, "fiber_g": 3},
            {"name": "Oatmeal with berries and almonds", "calories": 350, "protein_g": 12, "carbs_g": 55, "fat_g": 10, "fiber_g": 10},
            {"name": "Greek yogurt parfait with granola", "calories": 380, "protein_g": 20, "carbs_g": 45, "fat_g": 12, "fiber_g": 5},
            {"name": "Greek yogurt protein bowl with berries", "calories": 430, "protein_g": 40, "carbs_g": 42, "fat_g": 10, "fiber_g": 8},
        ],
        "lunch": [
            {"name": "Grilled chicken salad with quinoa", "calories": 450, "protein_g": 40, "carbs_g": 35, "fat_g": 15, "fiber_g": 8},
            {"name": "Turkey wrap with vegetables", "calories": 420, "protein_g": 35, "carbs_g": 40, "fat_g": 12, "fiber_g": 6},
            {"name": "Tuna salad with mixed greens", "calories": 380, "protein_g": 35, "carbs_g": 20, "fat_g": 18, "fiber_g": 4},
        ],
        "dinner": [
            {"name": "Salmon with brown rice and broccoli", "calories": 550, "protein_g": 40, "carbs_g": 45, "fat_g": 22, "fiber_g": 8},
            {"name": "Chicken stir-fry with vegetables", "calories": 480, "protein_g": 38, "carbs_g": 40, "fat_g": 18, "fiber_g": 7},
            {"name": "Lean beef with sweet potato", "calories": 520, "protein_g": 42, "carbs_g": 48, "fat_g": 16, "fiber_g": 7},
        ],
        "snack": [
            {"name": "Apple with peanut butter", "calories": 200, "protein_g": 7, "carbs_g": 22, "fat_g": 10, "fiber_g": 5},
            {"name": "Greek yogurt", "calories": 120, "protein_g": 15, "carbs_g": 10, "fat_g": 0, "fiber_g": 0},
            {"name": "Handful of almonds", "calories": 160, "protein_g": 6, "carbs_g": 6, "fat_g": 14, "fiber_g": 3},
        ],
    },
    "vegetarian": {
        "breakfast": [
            {"name": "Vegetable omelet with cheese", "calories": 380, "protein_g": 22, "carbs_g": 15, "fat_g": 24, "fiber_g": 3},
            {"name": "Oatmeal with protein powder", "calories": 350, "protein_g": 25, "carbs_g": 50, "fat_g": 8, "fiber_g": 8},
            {"name": "Cottage cheese protein bowl with berries", "calories": 390, "protein_g": 36, "carbs_g": 38, "fat_g": 9, "fiber_g": 6},
        ],
        "lunch": [
            {"name": "Lentil soup with whole grain bread", "calories": 420, "protein_g": 18, "carbs_g": 65, "fat_g": 10, "fiber_g": 16},
            {"name": "Caprese salad with quinoa", "calories": 400, "protein_g": 16, "carbs_g": 45, "fat_g": 18, "fiber_g": 6},
        ],
        "dinner": [
            {"name": "Tofu stir-fry with brown rice", "calories": 480, "protein_g": 22, "carbs_g": 55, "fat_g": 18, "fiber_g": 10},
            {"name": "Vegetable curry with chickpeas", "calories": 450, "protein_g": 18, "carbs_g": 60, "fat_g": 16, "fiber_g": 14},
        ],
        "snack": [
            {"name": "Hummus with vegetables", "calories": 180, "protein_g": 6, "carbs_g": 18, "fat_g": 10, "fiber_g": 6},
            {"name": "Cottage cheese with fruit", "calories": 150, "protein_g": 14, "carbs_g": 15, "fat_g": 3, "fiber_g": 3},
        ],
    },
    "vegan": {
        "breakfast": [
            {"name": "Tofu scramble with vegetables", "calories": 350, "protein_g": 20, "carbs_g": 25, "fat_g": 18, "fiber_g": 6},
            {"name": "Oatmeal with almond milk and banana", "calories": 320, "protein_g": 10, "carbs_g": 58, "fat_g": 8, "fiber_g": 9},
            {"name": "Tofu and soy yogurt protein bowl", "calories": 440, "protein_g": 32, "carbs_g": 40, "fat_g": 16, "fiber_g": 7},
        ],
        "lunch": [
            {"name": "Buddha bowl with quinoa and chickpeas", "calories": 450, "protein_g": 18, "carbs_g": 65, "fat_g": 14, "fiber_g": 15},
            {"name": "Lentil salad with tahini dressing", "calories": 420, "protein_g": 20, "carbs_g": 50, "fat_g": 16, "fiber_g": 16},
        ],
        "dinner": [
            {"name": "Tempeh stir-fry with vegetables", "calories": 480, "protein_g": 25, "carbs_g": 45, "fat_g": 20, "fiber_g": 11},
            {"name": "Black bean tacos with avocado", "calories": 460, "protein_g": 18, "carbs_g": 55, "fat_g": 18, "fiber_g": 15},
        ],
        "snack": [
            {"name": "Mixed nuts", "calories": 170, "protein_g": 6, "carbs_g": 7, "fat_g": 15, "fiber_g": 3},
            {"name": "Apple with almond butter", "calories": 190, "protein_g": 5, "carbs_g": 24, "fat_g": 9, "fiber_g": 6},
        ],
    },
    "pescatarian": {
        "breakfast": [
            {"name": "Smoked salmon with cream cheese on bagel", "calories": 420, "protein_g": 22, "carbs_g": 35, "fat_g": 20, "fiber_g": 3},
            {"name": "Greek yogurt with granola", "calories": 360, "protein_g": 18, "carbs_g": 48, "fat_g": 10, "fiber_g": 4},
        ],
        "lunch": [
            {"name": "Tuna salad with mixed greens", "calories": 380, "protein_g": 35, "carbs_g": 20, "fat_g": 18, "fiber_g": 4},
            {"name": "Shrimp and vegetable stir-fry", "calories": 350, "protein_g": 30, "carbs_g": 30, "fat_g": 12, "fiber_g": 6},
        ],
        "dinner": [
            {"name": "Baked cod with quinoa and vegetables", "calories": 450, "protein_g": 40, "carbs_g": 40, "fat_g": 12, "fiber_g": 8},
            {"name": "Salmon with roasted vegetables", "calories": 500, "protein_g": 38, "carbs_g": 25, "fat_g": 26, "fiber_g": 6},
        ],
        "snack": [
            {"name": "Sardines on crackers", "calories": 180, "protein_g": 15, "carbs_g": 12, "fat_g": 8, "fiber_g": 1},
            {"name": "Greek yogurt", "calories": 120, "protein_g": 15, "carbs_g": 10, "fat_g": 0, "fiber_g": 0},
        ],
    },
}


# Template names are presentation text, not a reliable allergy/restriction source.
# Keep the matching vocabulary separate and internal so a renamed display string
# cannot silently make an unsafe option eligible.
_INGREDIENTS_BY_MEAL_NAME = {
    "Scrambled eggs with toast": {"eggs", "gluten", "wheat"},
    "Oatmeal with berries and almonds": {"oats", "berries", "almonds", "tree nuts"},
    "Greek yogurt parfait with granola": {"dairy", "milk", "yogurt", "gluten", "oats"},
    "Greek yogurt protein bowl with berries": {"dairy", "milk", "yogurt", "berries"},
    "Grilled chicken salad with quinoa": {"chicken", "poultry", "quinoa", "vegetables"},
    "Turkey wrap with vegetables": {"turkey", "poultry", "gluten", "wheat", "vegetables"},
    "Tuna salad with mixed greens": {"tuna", "fish", "vegetables"},
    "Salmon with brown rice and broccoli": {"salmon", "fish", "rice", "vegetables", "broccoli"},
    "Chicken stir-fry with vegetables": {"chicken", "poultry", "vegetables", "soy"},
    "Lean beef with sweet potato": {"beef", "red meat", "sweet potato"},
    "Apple with peanut butter": {"apple", "peanuts", "peanut"},
    "Greek yogurt": {"dairy", "milk", "yogurt"},
    "Handful of almonds": {"almonds", "tree nuts"},
    "Vegetable omelet with cheese": {"eggs", "dairy", "milk", "cheese", "vegetables"},
    "Oatmeal with protein powder": {"oats", "dairy", "milk"},
    "Cottage cheese protein bowl with berries": {"dairy", "milk", "cheese", "berries"},
    "Lentil soup with whole grain bread": {"lentils", "gluten", "wheat"},
    "Caprese salad with quinoa": {"dairy", "milk", "cheese", "quinoa", "vegetables"},
    "Tofu stir-fry with brown rice": {"tofu", "soy", "rice", "vegetables"},
    "Vegetable curry with chickpeas": {"chickpeas", "legumes", "vegetables"},
    "Hummus with vegetables": {"chickpeas", "legumes", "sesame", "vegetables"},
    "Cottage cheese with fruit": {"dairy", "milk", "cheese", "fruit"},
    "Tofu scramble with vegetables": {"tofu", "soy", "vegetables"},
    "Oatmeal with almond milk and banana": {"oats", "almonds", "tree nuts", "banana"},
    "Tofu and soy yogurt protein bowl": {"tofu", "soy", "yogurt", "berries"},
    "Buddha bowl with quinoa and chickpeas": {"quinoa", "chickpeas", "legumes", "vegetables"},
    "Lentil salad with tahini dressing": {"lentils", "legumes", "sesame", "tahini", "vegetables"},
    "Tempeh stir-fry with vegetables": {"tempeh", "soy", "vegetables"},
    "Black bean tacos with avocado": {"black beans", "legumes", "avocado", "corn"},
    "Energy balls with dates and nuts": {"dates", "tree nuts", "nuts"},
    "Roasted chickpeas": {"chickpeas", "legumes"},
}


def _matches_exclusion(ingredients: set[str], exclusions: set[str]) -> bool:
    """Return whether an explicit ingredient tag matches an excluded food."""
    return any(
        exclusion == ingredient
        or exclusion in ingredient
        or ingredient in exclusion
        for exclusion in exclusions
        for ingredient in ingredients
    )


def _safe_options(options: list[dict], exclusions: set[str]) -> list[dict]:
    safe_options = []
    for option in options:
        ingredients = _INGREDIENTS_BY_MEAL_NAME.get(option["name"])
        # An untagged template cannot be proven safe for an exclusion request.
        if ingredients is not None and not _matches_exclusion(ingredients, exclusions):
            safe_options.append(option)
    return safe_options


def select_meal(
    meal_type: str,
    dietary_preference: str = "omnivore",
    *,
    max_calories: int | None = None,
    min_protein_g: int = 0,
    min_carbs_g: int = 0,
    min_fiber_g: int = 0,
    min_fat_g: int = 0,
    max_fat_g: int | None = None,
    prioritize_fiber: bool = False,
    allergies: list[str] | None = None,
    dietary_restrictions: list[str] | None = None,
) -> dict | None:
    """Return a safe meal meeting nutrient constraints, ranked by protein or fiber."""
    exclusions = {
        item.strip().casefold()
        for item in [*(allergies or []), *(dietary_restrictions or [])]
        if item.strip()
    }
    templates = MEAL_TEMPLATES.get(dietary_preference, MEAL_TEMPLATES["omnivore"])
    eligible = [
        option
        for option in _safe_options(templates.get(meal_type, []), exclusions)
        if (max_calories is None or option["calories"] <= max_calories)
        and option["protein_g"] >= min_protein_g
        and option["carbs_g"] >= min_carbs_g
        and option["fiber_g"] >= min_fiber_g
        and option["fat_g"] >= min_fat_g
        and (max_fat_g is None or option["fat_g"] <= max_fat_g)
    ]
    if not eligible:
        return None
    if prioritize_fiber:
        return max(
            eligible,
            key=lambda option: (option["fiber_g"], option["protein_g"], option["carbs_g"], -option["calories"]),
        )
    return max(eligible, key=lambda option: (option["protein_g"], -option["calories"]))


def select_breakfast(
    dietary_preference: str = "omnivore",
    *,
    max_calories: int,
    min_protein_g: int,
    allergies: list[str] | None = None,
    dietary_restrictions: list[str] | None = None,
) -> dict | None:
    """Return the highest-protein safe breakfast within explicit user constraints."""
    return select_meal(
        "breakfast",
        dietary_preference,
        max_calories=max_calories,
        min_protein_g=min_protein_g,
        allergies=allergies,
        dietary_restrictions=dietary_restrictions,
    )


def generate_meal_plan(
    macro_targets: dict,
    dietary_preference: str = "omnivore",
    meals_per_day: int = 3,
    allergies: list[str] | None = None,
    dietary_restrictions: list[str] | None = None,
) -> dict | None:
    """
    Generate a simple meal plan aligned with macro targets.

    Args:
        macro_targets: dict with calories, protein_g, carbs_g, fat_g
        dietary_preference: omnivore, vegetarian, vegan, pescatarian
        meals_per_day: Number of meals (3 = breakfast/lunch/dinner, 4 = +snack)
        allergies: List of allergens to avoid.
        dietary_restrictions: List of foods or ingredients to avoid.

    Returns:
        Dict with meals and totals, or None if no complete safe plan is available.
    """
    # Get meal templates for dietary preference
    templates = MEAL_TEMPLATES.get(dietary_preference, MEAL_TEMPLATES["omnivore"])
    exclusions = {
        item.strip().casefold()
        for item in [*(allergies or []), *(dietary_restrictions or [])]
        if item.strip()
    }

    # Simple distribution: 30% breakfast, 35% lunch, 35% dinner, 0-10% snacks
    target_calories = macro_targets["calories"]

    meal_plan = {}
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0

    # Breakfast (30%)
    if meals_per_day >= 1:
        breakfast_options = _safe_options(templates.get("breakfast", []), exclusions)
        if not breakfast_options:
            return None
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
        lunch_options = _safe_options(templates.get("lunch", []), exclusions)
        if not lunch_options:
            return None
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
        dinner_options = _safe_options(templates.get("dinner", []), exclusions)
        if not dinner_options:
            return None
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
        snack_options = _safe_options(templates.get("snack", []), exclusions)
        if not snack_options:
            return None
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
