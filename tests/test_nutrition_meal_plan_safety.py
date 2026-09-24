from services.nutrition_agent.app.meal_plan_safety import assess_meal_plan_safety


def meal(food_cache_id=1):
    return {"items": [{"food_name": "Oat bar", "food_cache_id": food_cache_id}]}


def test_known_allergen_conflict_blocks_meal_plan():
    meals, warnings = assess_meal_plan_safety(
        [meal()],
        {"allergies": ["Milk"], "dietary_restrictions": []},
        {1: {"allergen_status": "known", "allergen_data": {"contains": ["milk"]}}},
    )

    assert meals[0]["safety_status"] == "blocked"
    assert "confirmed allergy milk" in meals[0]["safety_warnings"][0]
    assert warnings == meals[0]["safety_warnings"]


def test_unknown_or_unclassified_food_requires_review_without_dietary_warnings():
    meals, _ = assess_meal_plan_safety(
        [meal(), meal(food_cache_id=None)],
        {"allergies": [], "dietary_restrictions": ["vegan"]},
        {1: {"allergen_status": "unknown", "allergen_data": None}},
    )

    assert [meal["safety_status"] for meal in meals] == [
        "review_required",
        "review_required",
    ]
    assert meals[0]["safety_warnings"] == [
        "Oat bar: allergen metadata is unknown; review required."
    ]


def test_fully_known_compatible_food_is_safe():
    meals, warnings = assess_meal_plan_safety(
        [meal()],
        {"allergies": ["milk"], "dietary_restrictions": []},
        {1: {"allergen_status": "known", "allergen_data": {"contains": ["oats"]}}},
    )

    assert meals[0]["safety_status"] == "safe"
    assert warnings == []
