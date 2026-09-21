def log_meal(description: str) -> str:
    """Request the structured, user-scoped confirmation required to log a meal.

    The specialist process has no authenticated user identity, so it must never
    write a shared JSON record or impersonate a user. The Nutrition page/API is
    the authoritative PostgreSQL-backed logging path.
    """
    description = description.strip()
    return (
        "Meal logging needs confirmation in Nutrition before it is saved. "
        f"I heard: {description}. Please confirm the meal type and portion "
        "(preferably grams), then use the Nutrition Meal Log to save it."
    )
