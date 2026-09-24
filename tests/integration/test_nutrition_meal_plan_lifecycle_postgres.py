"""Persisted meal-plan lifecycle coverage against PostgreSQL."""

import asyncio
import json
from datetime import date
from uuid import uuid4

import pytest
from conftest import create_target, create_user, planned_meal
from nutrition_agent_app.schemas import MealPlanCreateRequest
from nutrition_agent_app.service import (
    NutritionMealPlanSafetyError,
    NutritionMealPlanTransitionError,
    NutritionNotFoundError,
    NutritionService,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integration


def payload(
    user_id: int,
    target_snapshot_id: int,
    start: date,
    end: date,
    food_cache_id: int | None = None,
) -> MealPlanCreateRequest:
    meal = planned_meal(food_cache_id)
    meal["planned_date"] = start
    return MealPlanCreateRequest(
        user_id=user_id,
        target_snapshot_id=target_snapshot_id,
        start_date=start,
        end_date=end,
        generated_plan={"strategy": "integration"},
        planned_meals=[meal],
    )


async def create_draft(
    session: AsyncSession, plan_payload: MealPlanCreateRequest
) -> dict:
    service = NutritionService(session)
    created = await service.create_meal_plan(plan_payload.user_id, plan_payload)
    await session.commit()
    return created


@pytest.mark.asyncio
async def test_private_schema_sets_the_persisted_plan_default(postgres_session_factory):
    async with postgres_session_factory() as session:
        user_id = await create_user(session, "default@example.com")
        target_id = await create_target(session, user_id)
        result = await session.execute(
            text("""
            INSERT INTO nutrition_meal_plans
                (user_id, target_snapshot_id, start_date, end_date, version)
            VALUES (:user_id, :target_id, '2026-09-22', '2026-09-22', 1)
            RETURNING status
        """),
            {"user_id": user_id, "target_id": target_id},
        )
        await session.commit()
        assert result.scalar_one() == "draft"


@pytest.mark.asyncio
async def test_confirm_supersedes_overlaps_but_retains_non_overlapping_active_plans(
    postgres_session_factory,
):
    async with postgres_session_factory() as session:
        user_id = await create_user(session, "overlap@example.com")
        target_id = await create_target(session, user_id)
        await session.commit()
        first = await create_draft(
            session, payload(user_id, target_id, date(2026, 9, 22), date(2026, 9, 24))
        )
        second = await create_draft(
            session, payload(user_id, target_id, date(2026, 9, 23), date(2026, 9, 25))
        )
        third = await create_draft(
            session, payload(user_id, target_id, date(2026, 9, 26), date(2026, 9, 27))
        )
        service = NutritionService(session)
        await service.confirm_meal_plan(user_id, first["id"])
        await service.confirm_meal_plan(user_id, third["id"])
        confirmed = await service.confirm_meal_plan(user_id, second["id"])
        await session.commit()
        statuses = dict(
            (
                await session.execute(
                    text("SELECT id, status FROM nutrition_meal_plans")
                )
            ).all()
        )
        assert confirmed["status"] == "active"
        assert statuses == {
            first["id"]: "superseded",
            second["id"]: "active",
            third["id"]: "active",
        }


@pytest.mark.asyncio
async def test_confirmation_rechecks_persisted_allergen_data_and_leaves_draft(
    postgres_session_factory,
):
    async with postgres_session_factory() as session:
        user_id = await create_user(session, "allergy@example.com")
        target_id = await create_target(session, user_id)
        food_id = (
            await session.execute(
                text("""
            INSERT INTO nutrition_food_cache (
                provider, provider_food_id, description, allergen_data, allergen_status, raw_response
            ) VALUES ('test', :provider_food_id, 'Oats', '{"contains": []}', 'known', '{}') RETURNING id
        """),
                {"provider_food_id": f"meal-plan-safety-oats-{uuid4()}"},
            )
        ).scalar_one()
        await session.commit()
        draft = await create_draft(
            session,
            payload(user_id, target_id, date(2026, 9, 22), date(2026, 9, 22), food_id),
        )
        await session.execute(
            text(
                'UPDATE nutrition_food_cache SET allergen_data = \'{"contains": ["milk"]}\' WHERE id = :id'
            ),
            {"id": food_id},
        )
        await session.commit()
        with pytest.raises(NutritionMealPlanSafetyError):
            await NutritionService(session).confirm_meal_plan(
                user_id, draft["id"], profile={"allergies": ["milk"]}
            )
        await session.rollback()
        status = (
            await session.execute(
                text("SELECT status FROM nutrition_meal_plans WHERE id = :id"),
                {"id": draft["id"]},
            )
        ).scalar_one()
        assert status == "draft"


@pytest.mark.asyncio
async def test_transitions_are_owned_and_idempotency_is_persisted(
    postgres_session_factory,
):
    async with postgres_session_factory() as session:
        owner_id = await create_user(session, "owner@example.com")
        other_id = await create_user(session, "other@example.com")
        target_id = await create_target(session, owner_id)
        await session.commit()
        draft = await create_draft(
            session, payload(owner_id, target_id, date(2026, 9, 22), date(2026, 9, 22))
        )
        with pytest.raises(NutritionNotFoundError):
            await NutritionService(session).confirm_meal_plan(other_id, draft["id"])
        await session.rollback()
        service = NutritionService(session)
        first = await service.idempotent(
            owner_id,
            "confirm_meal_plan",
            "same-key",
            {"meal_plan_id": draft["id"]},
            lambda: service.confirm_meal_plan(owner_id, draft["id"]),
        )
        await session.commit()
    async with postgres_session_factory() as replay_session:
        replay_service = NutritionService(replay_session)
        replay = await replay_service.idempotent(
            owner_id,
            "confirm_meal_plan",
            "same-key",
            {"meal_plan_id": draft["id"]},
            lambda: replay_service.confirm_meal_plan(owner_id, draft["id"]),
        )
        count = (
            await replay_session.execute(
                text(
                    "SELECT count(*) FROM nutrition_idempotency_keys WHERE user_id = :id AND operation = 'confirm_meal_plan'"
                ),
                {"id": owner_id},
            )
        ).scalar_one()
        assert replay == json.loads(json.dumps(first, default=str))
        assert count == 1
        with pytest.raises(NutritionMealPlanTransitionError):
            await replay_service.confirm_meal_plan(owner_id, draft["id"])
        await replay_session.rollback()


@pytest.mark.asyncio
async def test_concurrent_creation_allocates_distinct_versions(
    postgres_session_factory: async_sessionmaker[AsyncSession],
):
    async with postgres_session_factory() as setup_session:
        user_id = await create_user(setup_session, "versions@example.com")
        target_id = await create_target(setup_session, user_id)
        await setup_session.commit()

    async def create() -> dict:
        async with postgres_session_factory() as session:
            created = await create_draft(
                session,
                payload(user_id, target_id, date(2026, 9, 22), date(2026, 9, 22)),
            )
            return created

    created = await asyncio.gather(create(), create())
    assert sorted(plan["version"] for plan in created) == [1, 2]


@pytest.mark.asyncio
async def test_concurrent_overlapping_confirmation_leaves_one_active_plan(
    postgres_session_factory: async_sessionmaker[AsyncSession],
):
    async with postgres_session_factory() as setup_session:
        user_id = await create_user(setup_session, "concurrent@example.com")
        target_id = await create_target(setup_session, user_id)
        await setup_session.commit()
        first = await create_draft(
            setup_session,
            payload(user_id, target_id, date(2026, 9, 22), date(2026, 9, 24)),
        )
        second = await create_draft(
            setup_session,
            payload(user_id, target_id, date(2026, 9, 23), date(2026, 9, 25)),
        )

    async def confirm(plan_id: int) -> None:
        async with postgres_session_factory() as session:
            await NutritionService(session).confirm_meal_plan(user_id, plan_id)
            await session.commit()

    await asyncio.gather(confirm(first["id"]), confirm(second["id"]))
    async with postgres_session_factory() as session:
        statuses = [
            row[0]
            for row in (
                await session.execute(
                    text("SELECT status FROM nutrition_meal_plans ORDER BY id")
                )
            ).all()
        ]
        assert sorted(statuses) == ["active", "superseded"]
