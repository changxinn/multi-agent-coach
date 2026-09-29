"""Conservative, auditable triage for food compatibility review queues."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

CLASSIFIER_VERSION = "rules_only_triage_v1"
POLICY_VERSION = "unprocessed_whole_food_v1"

_PLANT_PREFIXES = (
    "apple",
    "apricot",
    "asparagus",
    "avocado",
    "banana",
    "beans",
    "beets",
    "blackberries",
    "blueberries",
    "broccoli",
    "cabbage",
    "carrots",
    "cauliflower",
    "celery",
    "cherries",
    "cucumber",
    "eggplant",
    "grapes",
    "kale",
    "lemon",
    "lentils",
    "lettuce",
    "mango",
    "mushrooms",
    "onions",
    "orange",
    "peach",
    "peas",
    "pear",
    "peppers",
    "pineapple",
    "potatoes",
    "raspberries",
    "rice",
    "spinach",
    "squash",
    "strawberries",
    "sweet potato",
    "tomato",
    "watermelon",
    "zucchini",
)
_AMBIGUOUS_TERMS = (
    "babyfood",
    "branded",
    "canned",
    "cooked",
    "dried",
    "flavored",
    "flavoured",
    "frozen",
    "juice",
    "mix",
    "prepared",
    "seasoned",
)


@dataclass(frozen=True)
class CompatibilityCandidate:
    """A preliminary classification that requires human review before use."""

    food_cache_id: int
    review_status: str
    allergen_status: str
    known_allergens: list[str]
    strict_suitability: dict[str, str]
    evidence: dict[str, Any]
    confidence: float
    classifier_version: str
    policy_version: str
    input_fingerprint: str

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_food_input(food: dict[str, Any]) -> dict[str, Any]:
    """Return the source fields that determine a repeatable triage result."""
    return {
        "id": int(food["id"]),
        "provider": str(food.get("provider") or ""),
        "provider_food_id": str(food.get("provider_food_id") or ""),
        "description": str(food.get("description") or ""),
        "raw_response": food.get("raw_response"),
    }


def food_input_fingerprint(food: dict[str, Any]) -> str:
    """Hash canonical source data so unchanged records are not re-triaged."""
    payload = json.dumps(
        canonical_food_input(food), sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_food_for_review(food: dict[str, Any]) -> CompatibilityCandidate:
    """Create conservative non-approved metadata without safety/certification inference."""
    description = str(food.get("description") or "").strip()
    description_key = description.casefold()
    is_raw_plant_candidate = (
        "raw" in description_key
        and description_key.startswith(_PLANT_PREFIXES)
        and not any(term in description_key for term in _AMBIGUOUS_TERMS)
    )
    status = "auto_classified" if is_raw_plant_candidate else "review_required"
    scope = (
        "potential raw single-ingredient plant food; human evidence review required"
        if is_raw_plant_candidate
        else "ambiguous, processed, animal-derived, or insufficiently described food; review required"
    )
    return CompatibilityCandidate(
        food_cache_id=int(food["id"]),
        review_status=status,
        allergen_status="unknown",
        known_allergens=[],
        strict_suitability={},
        evidence={
            "source": "USDA FoodData Central description",
            "description": description,
            "scope": scope,
            "certification": "not evaluated; no certification claim",
        },
        confidence=0.8 if is_raw_plant_candidate else 0.0,
        classifier_version=CLASSIFIER_VERSION,
        policy_version=POLICY_VERSION,
        input_fingerprint=food_input_fingerprint(food),
    )
