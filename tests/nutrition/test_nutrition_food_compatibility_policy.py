import pytest

from services.nutrition_agent.app.food_compatibility_policy import (
    STRICT_OPTIONS,
    allergen_values,
    compatibility_failure_reason,
    normalise_values,
    selected_strict_options,
    validate_human_review,
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


def test_policy_normalises_scalar_aliases_and_nested_allergen_metadata():
    assert normalise_values("Plant based") == {"vegan"}
    assert normalise_values(None) == set()
    assert allergen_values({"primary": ["Milk", {"secondary": "tree nuts"}]}) == {
        "milk",
        "tree_nuts",
    }


def test_approved_review_requires_complete_known_evidence_backed_decision():
    suitability = {option: "suitable" for option in STRICT_OPTIONS}

    assert validate_human_review(
        review_status="approved",
        allergen_status="known",
        known_allergens=["Milk", "milk"],
        strict_suitability=suitability,
        evidence={"source": "manufacturer label"},
        confidence=0.95,
    ) == ["milk"]

    for field, value, message in (
        ("allergen_status", "unknown", "known allergen metadata"),
        ("evidence", {}, "requires evidence"),
        ("confidence", None, "requires confidence"),
    ):
        values = {
            "review_status": "approved",
            "allergen_status": "known",
            "known_allergens": [],
            "strict_suitability": suitability,
            "evidence": {"source": "manufacturer label"},
            "confidence": 0.95,
        }
        values[field] = value
        try:
            validate_human_review(**values)
        except ValueError as error:
            assert message in str(error)
        else:
            raise AssertionError(f"Expected {field} to be rejected")


def test_approved_review_rejects_unknown_missing_and_invalid_strict_options():
    base = {
        "review_status": "approved",
        "allergen_status": "known",
        "known_allergens": [],
        "evidence": {"source": "manufacturer label"},
        "confidence": 0.95,
    }

    with pytest.raises(ValueError, match="Unknown strict suitability"):
        validate_human_review(
            **base,
            strict_suitability={
                **{key: "suitable" for key in STRICT_OPTIONS},
                "custom": "suitable",
            },
        )
    with pytest.raises(ValueError, match="every strict suitability"):
        validate_human_review(**base, strict_suitability={})
    with pytest.raises(ValueError, match="must be suitable or unsuitable"):
        validate_human_review(
            **base, strict_suitability={key: "unknown" for key in STRICT_OPTIONS}
        )


def test_compatibility_reason_requires_known_allergens_and_strict_metadata():
    assert (
        compatibility_failure_reason(approved_metadata(allergen_status="unknown"), {})
        == "allergen metadata is not known"
    )
    assert (
        compatibility_failure_reason(approved_metadata(strict_suitability=[]), {})
        == "strict compatibility metadata is missing"
    )
