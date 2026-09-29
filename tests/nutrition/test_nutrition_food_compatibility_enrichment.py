from services.nutrition_agent.app.food_compatibility_enrichment import (
    classify_food_for_review,
    food_input_fingerprint,
)


def food(**overrides):
    return {
        "id": 12,
        "provider": "usda",
        "provider_food_id": "321360",
        "description": "Tomatoes, red, ripe, raw, year round average",
        "raw_response": {"fdcId": 321360},
        **overrides,
    }


def test_input_fingerprint_is_repeatable_and_tracks_source_changes():
    assert food_input_fingerprint(food()) == food_input_fingerprint(food())
    assert food_input_fingerprint(
        food(description="Tomatoes, cooked")
    ) != food_input_fingerprint(food())


def test_obvious_raw_plant_food_is_only_auto_classified_for_human_review():
    candidate = classify_food_for_review(food())

    assert candidate.review_status == "auto_classified"
    assert candidate.allergen_status == "unknown"
    assert candidate.known_allergens == []
    assert candidate.strict_suitability == {}
    assert (
        candidate.evidence["certification"] == "not evaluated; no certification claim"
    )


def test_prepared_or_animal_food_requires_review_and_is_never_approved():
    for description in (
        "Tomatoes, canned, stewed",
        "Chicken, broilers or fryers, meat only, cooked, roasted",
        "Commercial hummus, prepared",
    ):
        candidate = classify_food_for_review(food(description=description))
        assert candidate.review_status == "review_required"
        assert candidate.review_status != "approved"
