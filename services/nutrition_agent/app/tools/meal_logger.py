"""Meal logging tool."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def log_meal(
    user_id: int,
    meal_type: str,
    description: str,
    calories: int = None,
    protein_g: float = None,
    carbs_g: float = None,
    fat_g: float = None,
) -> dict:
    """
    Log a meal (placeholder - actual DB logging in repository).

    This function validates input and prepares data for database insertion.
    Actual database operations are handled by the repository layer.

    Args:
        user_id: User ID
        meal_type: breakfast, lunch, dinner, or snack
        description: Meal description
        calories: Optional calorie count
        protein_g: Optional protein in grams
        carbs_g: Optional carbs in grams
        fat_g: Optional fat in grams

    Returns:
        dict with meal data and validation status
    """
    # Validate meal type
    valid_meal_types = ["breakfast", "lunch", "dinner", "snack"]
    if meal_type.lower() not in valid_meal_types:
        return {
            "success": False,
            "error": f"Invalid meal type. Must be one of: {', '.join(valid_meal_types)}",
        }

    # Validate description
    if not description or len(description.strip()) == 0:
        return {"success": False, "error": "Meal description is required"}

    if len(description) > 1000:
        return {"success": False, "error": "Description too long (max 1000 characters)"}

    # Validate macros if provided
    if calories is not None and calories <= 0:
        return {"success": False, "error": "Calories must be positive"}

    for macro_name, macro_value in [
        ("protein", protein_g),
        ("carbs", carbs_g),
        ("fat", fat_g),
    ]:
        if macro_value is not None and macro_value < 0:
            return {"success": False, "error": f"{macro_name} must be non-negative"}

    # Prepare meal data
    meal_data = {
        "user_id": user_id,
        "meal_type": meal_type.lower(),
        "description": description.strip(),
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "logged_at": datetime.utcnow().isoformat(),
    }

    return {
        "success": True,
        "meal_data": meal_data,
        "message": f"Meal logged: {meal_type} - {description[:50]}...",
    }
