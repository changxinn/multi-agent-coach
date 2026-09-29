from services.nutrition_agent.app.meal_plan_safety import assess_meal_plan_safety


def meal(food_cache_id=1):
    return {"items": [{"food_name": "Oat bar", "food_cache_id": food_cache_id}]}


def approved_metadata(*, allergens=(), strict_suitability=None):
    return {
        "review_status": "approved",
        "allergen_status": "known",
        "known_allergens": list(allergens),
        "strict_suitability": strict_suitability or {},
    }


def test_known_allergen_conflict_blocks_meal_plan():
    meals, warnings = assess_meal_plan_safety(
        [meal()],
        {"allergies": ["Milk"], "dietary_restrictions": []},
        {1: approved_metadata(allergens=["milk"])},
    )

    assert meals[0]["safety_status"] == "blocked"
    assert "confirmed allergy milk" in meals[0]["safety_warnings"][0]
    assert warnings == meals[0]["safety_warnings"]


def test_unapproved_or_unclassified_food_is_blocked_for_a_saved_profile():
    meals, _ = assess_meal_plan_safety(
        [meal(), meal(food_cache_id=None)],
        {"allergies": [], "dietary_restrictions": ["vegan"]},
        {1: {"review_status": "pending", "allergen_status": "unknown"}},
    )

    assert [meal["safety_status"] for meal in meals] == [
        "blocked",
        "review_required",
    ]
    assert meals[0]["safety_warnings"] == [
        "Oat bar: compatibility metadata is not approved."
    ]


def test_fully_known_compatible_food_is_safe():
    meals, warnings = assess_meal_plan_safety(
        [meal()],
        {"allergies": ["milk"], "dietary_restrictions": []},
        {1: approved_metadata(allergens=["oats"])},
    )

    assert meals[0]["safety_status"] == "safe"
    assert warnings == []


def test_strict_constraint_requires_an_explicit_suitable_status():
    meals, _ = assess_meal_plan_safety(
        [meal()],
        {
            "allergies": [],
            "dietary_preferences": ["vegetarian"],
            "dietary_restrictions": ["halal"],
        },
        {1: approved_metadata(strict_suitability={"vegetarian": "suitable"})},
    )

    assert meals[0]["safety_status"] == "blocked"
    assert "not approved for halal" in meals[0]["safety_warnings"][0]
