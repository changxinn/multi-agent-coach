"""TDEE (Total Daily Energy Expenditure) calculator using Mifflin-St Jeor equation."""


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def calculate_bmr(age: int, gender: str, weight_kg: float, height_cm: float) -> int:
    """
    Calculate Basal Metabolic Rate using Mifflin-St Jeor equation.

    Most accurate formula per research (Journal of the American Dietetic Association).

    Men: BMR = (10 × weight_kg) + (6.25 × height_cm) - (5 × age) + 5
    Women: BMR = (10 × weight_kg) + (6.25 × height_cm) - (5 × age) - 161

    Args:
        age: Age in years
        gender: 'male' or 'female'
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters

    Returns:
        BMR in calories per day
    """
    weight_component = 10 * weight_kg
    height_component = 6.25 * height_cm
    age_component = 5 * age

    if gender.lower() == "male":
        bmr = weight_component + height_component - age_component + 5
    elif gender.lower() == "female":
        bmr = weight_component + height_component - age_component - 161
    else:
        # Use average for 'other' or unknown
        bmr = weight_component + height_component - age_component - 78

    return round(bmr)


def calculate_tdee(
    age: int,
    gender: str,
    weight_kg: float,
    height_cm: float,
    activity_level: str,
) -> dict:
    """
    Calculate Total Daily Energy Expenditure.

    TDEE = BMR × Activity Multiplier

    Activity multipliers:
    - sedentary: 1.2 (little or no exercise)
    - light: 1.375 (light exercise 1-3 days/week)
    - moderate: 1.55 (moderate exercise 3-5 days/week)
    - active: 1.725 (hard exercise 6-7 days/week)
    - very_active: 1.9 (very hard exercise, physical job)

    Args:
        age: Age in years
        gender: 'male', 'female', or 'other'
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        activity_level: One of: sedentary, light, moderate, active, very_active

    Returns:
        dict with tdee, bmr, activity_multiplier, and formula
    """
    bmr = calculate_bmr(age, gender, weight_kg, height_cm)
    activity_multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
    tdee = round(bmr * activity_multiplier)

    return {
        "tdee": tdee,
        "bmr": bmr,
        "activity_multiplier": activity_multiplier,
        "formula": "Mifflin-St Jeor",
    }
