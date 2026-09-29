"""Fail-closed policy for automatic meal-plan food compatibility."""

from collections.abc import Iterable
from typing import Any

STRICT_OPTIONS = frozenset(
    {
        "vegetarian",
        "vegan",
        "pescatarian",
        "halal",
        "kosher",
        "gluten_free",
        "dairy_free",
        "egg_free",
        "soy_free",
        "nut_free",
        "no_pork",
        "no_beef",
        "alcohol_free",
    }
)
RANKING_ONLY_OPTIONS = frozenset(
    {
        "mediterranean",
        "plant_forward",
        "high_protein",
        "low_carb",
        "whole_food_focused",
        "spicy",
        "budget_friendly",
        "quick_prep",
    }
)
ADVISORY_OPTIONS = frozenset({"low_sodium", "low_fodmap"})
ALIASES = {
    "plant based": "vegan",
    "plant-based": "vegan",
    "vegetarian diet": "vegetarian",
    "gluten free": "gluten_free",
    "dairy free": "dairy_free",
    "milk free": "dairy_free",
    "egg free": "egg_free",
    "soy free": "soy_free",
    "nut free": "nut_free",
    "no pork": "no_pork",
    "pork free": "no_pork",
    "no beef": "no_beef",
    "beef free": "no_beef",
    "alcohol free": "alcohol_free",
    "plant forward": "plant_forward",
    "high protein": "high_protein",
    "low carb": "low_carb",
    "whole food focused": "whole_food_focused",
    "budget friendly": "budget_friendly",
    "quick prep": "quick_prep",
    "low sodium": "low_sodium",
    "low fodmap": "low_fodmap",
}


def normalise(value: Any) -> str:
    normalised = " ".join(str(value).casefold().replace("_", " ").split())
    return ALIASES.get(normalised, normalised.replace(" ", "_"))


def normalise_values(values: Any) -> set[str]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, dict)):
        values = [values] if values else []
    return {normalise(value) for value in values if str(value).strip()}


def selected_strict_options(profile: dict[str, Any] | None) -> set[str]:
    if not profile:
        return set()
    selected = set()
    for field in ("dietary_preferences", "dietary_restrictions"):
        selected.update(normalise_values(profile.get(field)))
    return selected & STRICT_OPTIONS


def allergen_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return normalise_values([value])
    if isinstance(value, dict):
        return set().union(*(allergen_values(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(allergen_values(item) for item in value))
    return set()


def normalise_allergens(values: list[str]) -> list[str]:
    """Return stable, non-empty allergy identifiers for reviewed metadata."""
    return sorted(normalise_values(values))


def validate_human_review(
    *,
    review_status: str,
    allergen_status: str,
    known_allergens: list[str],
    strict_suitability: dict[str, str],
    evidence: dict[str, Any],
    confidence: Any,
) -> list[str]:
    """Reject incomplete approval decisions before they can affect meal planning."""
    allergens = normalise_allergens(known_allergens)
    if review_status != "approved":
        return allergens
    if allergen_status != "known":
        raise ValueError("Approved compatibility requires known allergen metadata")
    if not evidence:
        raise ValueError("Approved compatibility requires evidence")
    if confidence is None:
        raise ValueError("Approved compatibility requires confidence")
    invalid = set(strict_suitability) - STRICT_OPTIONS
    if invalid:
        raise ValueError(
            f"Unknown strict suitability options: {', '.join(sorted(invalid))}"
        )
    missing = STRICT_OPTIONS - set(strict_suitability)
    if missing:
        raise ValueError(
            "Approved compatibility requires every strict suitability option"
        )
    if any(
        value not in {"suitable", "unsuitable"} for value in strict_suitability.values()
    ):
        raise ValueError("Strict suitability values must be suitable or unsuitable")
    return allergens


def compatibility_failure_reason(
    metadata: dict[str, Any] | None, profile: dict[str, Any] | None
) -> str | None:
    """Return a safe exclusion reason, or ``None`` only for approved compatibility."""
    if not metadata or metadata.get("review_status") != "approved":
        return "compatibility metadata is not approved"
    if metadata.get("allergen_status") != "known":
        return "allergen metadata is not known"
    allergies = normalise_values((profile or {}).get("allergies"))
    matches = allergies & allergen_values(metadata.get("known_allergens"))
    if matches:
        return f"conflicts with confirmed allergy {', '.join(sorted(matches))}"
    suitability = metadata.get("strict_suitability")
    if not isinstance(suitability, dict):
        return "strict compatibility metadata is missing"
    for option in sorted(selected_strict_options(profile)):
        if suitability.get(option) != "suitable":
            return f"is not approved for {option.replace('_', ' ')}"
    return None
