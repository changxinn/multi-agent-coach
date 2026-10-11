"""Persisted human compatibility-review workflow coverage against PostgreSQL."""

from uuid import uuid4

import pytest
from conftest import create_user
from nutrition_agent_app.schemas import CompatibilityReviewRequest
from nutrition_agent_app.service import NutritionService
from sqlalchemy import text

pytestmark = pytest.mark.integration


def approved_review(
    food_cache_id: int, reviewer_user_id: int
) -> CompatibilityReviewRequest:
    return CompatibilityReviewRequest(
        food_cache_id=food_cache_id,
        review_status="approved",
        allergen_status="known",
        known_allergens=["Milk Protein"],
        strict_suitability={
            "vegetarian": "suitable",
            "vegan": "unsuitable",
            "pescatarian": "suitable",
            "halal": "suitable",
            "kosher": "suitable",
            "gluten_free": "suitable",
            "dairy_free": "unsuitable",
            "egg_free": "suitable",
            "soy_free": "suitable",
            "nut_free": "suitable",
            "no_pork": "suitable",
            "no_beef": "suitable",
            "alcohol_free": "suitable",
        },
        evidence={"source": "integration label"},
        confidence="0.95",
        policy_version="compatibility_review_v1",
        review_note="Verified against manufacturer label.",
        reviewer_user_id=reviewer_user_id,
        reviewer_email="nutrition.admin@example.com",
    )


@pytest.mark.asyncio
async def test_human_review_updates_current_record_and_appends_immutable_history(
    postgres_session_factory,
):
    async with postgres_session_factory() as session:
        reviewer_user_id = await create_user(session, "nutrition.admin@example.com")
        food_cache_id = (
            await session.execute(
                text("""
                    INSERT INTO nutrition_food_cache (provider, provider_food_id, description, raw_response)
                    VALUES ('test', :provider_food_id, 'Review oats', '{}'::jsonb) RETURNING id
                """),
                {"provider_food_id": f"compatibility-review-{uuid4()}"},
            )
        ).scalar_one()
        await session.execute(
            text("""
                INSERT INTO nutrition_food_compatibility (food_cache_id, review_status)
                VALUES (:food_cache_id, 'pending')
            """),
            {"food_cache_id": food_cache_id},
        )

        result = await NutritionService(session).review_food_compatibility(
            approved_review(food_cache_id, reviewer_user_id)
        )
        await session.commit()
        history = await NutritionService(session).get_compatibility_review_history(
            food_cache_id
        )

    assert result["review_status"] == "approved"
    assert result["known_allergens"] == ["milk_protein"]
    assert result["reviewer_user_id"] == reviewer_user_id
    assert len(history) == 1
    assert history[0]["prior_review_status"] == "pending"
    assert history[0]["result_review_status"] == "approved"
    assert history[0]["reviewer_email"] == "nutrition.admin@example.com"
    assert history[0]["metadata_snapshot"]["known_allergens"] == ["milk_protein"]
