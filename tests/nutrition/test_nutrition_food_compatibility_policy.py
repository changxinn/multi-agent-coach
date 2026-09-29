from services.nutrition_agent.app.food_compatibility_policy import (
    compatibility_failure_reason,
    selected_strict_options,
)


def approved_metadata(**overrides):
    return {
        "review_status": "approved",
        "allergen_status": "known",
        "known_allergens": [],
        "strict_suitability": {
            "vegetarian": "suitable",
            "halal": "suitable",
            "dairy_free": "suitable",
        },
        **overrides,
    }


def test_vegetarian_halal_milk_allergy_requires_all_cumulative_approvals():
    profile = {
        "allergies": ["Milk"],
        "dietary_preferences": ["Vegetarian"],
        "dietary_restrictions": ["halal", "dairy free"],
    }

    assert compatibility_failure_reason(approved_metadata(), profile) is None
    assert compatibility_failure_reason(
        approved_metadata(known_allergens=["milk"]), profile
    ) == ("conflicts with confirmed allergy milk")
    assert "halal" in compatibility_failure_reason(
        approved_metadata(
            strict_suitability={"vegetarian": "suitable", "dairy_free": "suitable"}
        ),
        profile,
    )


def test_ranking_and_advisory_options_do_not_become_strict_exclusions():
    assert (
        selected_strict_options(
            {"dietary_preferences": ["Mediterranean", "quick prep", "low sodium"]}
        )
        == set()
    )


def test_unknown_or_unapproved_metadata_fails_closed():
    assert (
        compatibility_failure_reason(None, {})
        == "compatibility metadata is not approved"
    )
    assert (
        compatibility_failure_reason(approved_metadata(review_status="pending"), {})
        == "compatibility metadata is not approved"
    )
