from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from services.nutrition_agent.app import migrations
from services.nutrition_agent.app.migrations import (
    imported_food_cache_seed_exists,
    run_migrations,
    split_sql_statements,
)


def test_initial_schema_idempotently_adds_safety_review_acknowledgement_column():
    migration = (
        Path(__file__).parents[2]
        / "services/nutrition_agent/app/db/migrations/001_create_nutrition_schema.sql"
    ).read_text()

    assert "safety_review_acknowledged_at TIMESTAMPTZ" in migration
    assert (
        "ADD COLUMN IF NOT EXISTS safety_review_acknowledged_at TIMESTAMPTZ"
        in migration
    )


def test_child_targeted_food_cleanup_migration_removes_only_explicitly_targeted_products():
    migration = (
        Path(__file__).parents[2]
        / "services/nutrition_agent/app/db/migrations/006_remove_child_targeted_food_cache.sql"
    ).read_text()

    assert "DELETE FROM nutrition_food_cache" in migration
    assert "description ILIKE 'Babyfood,%'" in migration
    assert "description ILIKE 'Baby Toddler%'" in migration
    assert "description ILIKE 'Toddler%'" in migration
    assert "description ILIKE 'Infant formula,%'" in migration
    assert "description = 'Water, baby'" in migration
    assert "Carrots, baby" not in migration


def test_food_compatibility_schema_migration_is_idempotent_and_seeds_only_raw_foods():
    migration_dir = (
        Path(__file__).parents[2] / "services/nutrition_agent/app/db/migrations"
    )
    migration = (migration_dir / "007_create_food_compatibility_schema.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS nutrition_food_compatibility" in migration
    assert "REFERENCES nutrition_food_cache(id) ON DELETE CASCADE" in migration
    assert "review_status" in migration and "known_allergens" in migration
    assert "certification" in migration
    assert "description ILIKE '%raw%'" in migration
    assert "input_fingerprint" in migration
    assert "auto_classified" in migration and "review_required" in migration
    assert (
        "CREATE TABLE IF NOT EXISTS nutrition_food_compatibility_review_history"
        in migration
    )
    assert "metadata_snapshot JSONB NOT NULL" in migration
    assert "reviewer_user_id BIGINT NOT NULL" in migration
    assert "ix_nutrition_food_compatibility_review_queue" in migration


def test_food_triage_migration_applies_ordered_approved_system_policy():
    migration_dir = (
        Path(__file__).parents[2] / "services/nutrition_agent/app/db/migrations"
    )
    migration = (migration_dir / "008_auto_triage_food_compatibility.sql").read_text()

    assert "f.description ILIKE '%pork%'" in migration
    assert (
        "WHEN f.description ILIKE '%beef%' THEN 'usda_description_contains_beef_no_pork_v1'"
        in migration
    )
    assert "f.description ILIKE '%lamb%' OR f.description ILIKE '%mutton%'" in migration
    assert "f.description ILIKE '%fish%'" in migration
    assert "'usda_description_contains_pork_v2'" in migration
    assert "'usda_description_contains_beef_no_pork_v1'" in migration
    assert "'usda_description_contains_lamb_mutton_v1'" in migration
    assert "'usda_description_contains_fish_v1'" in migration
    for rule in (
        "usda_raw_broccoli_v1",
        "usda_zucchini_v1",
        "usda_raw_berries_banana_v1",
        "usda_yeast_v1",
        "usda_peanuts_v1",
        "usda_plain_water_v1",
        "usda_whey_protein_isolate_v1",
        "usda_black_beans_white_rice_v1",
        "usda_vegan_mayonnaise_v1",
        "usda_bread_v1",
        "usda_waffle_v1",
        "usda_rice_v1",
        "usda_coffee_v1",
        "usda_tea_v1",
    ):
        assert f"'{rule}'" in migration
    assert (
        "\\m(alcoholic|beer|wine|rum|whiskey|whisky|vodka|brandy|liqueur)\\M"
        in migration
    )
    assert "review_status = 'approved'" in migration
    assert "confidence = 0.500" in migration
    assert "allergen_status = 'known'" in migration
    for option in (
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
    ):
        assert f'"{option}":' in migration
    assert "system@nutrition-agent.local" in migration
    assert "INSERT INTO nutrition_food_compatibility_review_history" in migration


def test_food_compatibility_queue_backfill_enrolls_only_missing_cache_foods():
    migration_dir = (
        Path(__file__).parents[2] / "services/nutrition_agent/app/db/migrations"
    )
    migration = (
        migration_dir / "009_backfill_food_compatibility_review_queue.sql"
    ).read_text()

    assert "INSERT INTO nutrition_food_compatibility" in migration
    assert "FROM nutrition_food_cache f" in migration
    assert "'review_required'" in migration
    assert "'compatibility_queue_backfill_v1'" in migration
    assert "ON CONFLICT (food_cache_id) DO NOTHING" in migration


def test_backfilled_food_triage_is_limited_to_newly_enrolled_records():
    migration_dir = (
        Path(__file__).parents[2] / "services/nutrition_agent/app/db/migrations"
    )
    migration = (
        migration_dir / "010_auto_triage_backfilled_food_compatibility.sql"
    ).read_text()

    assert "c.review_status = 'review_required'" in migration
    assert "c.classifier_version = 'compatibility_queue_backfill_v1'" in migration
    assert "review_status = 'approved'" in migration
    assert "INSERT INTO nutrition_food_compatibility_review_history" in migration


def test_split_sql_statements_preserves_semicolons_in_sql_string_literals():
    statements = split_sql_statements(
        "INSERT INTO nutrition_food_cache (description, raw_response) "
        "VALUES ('Beans; cooked', '{\"note\":\"a; b\"}'::jsonb); "
        "SELECT 1;"
    )

    assert statements == [
        (
            "INSERT INTO nutrition_food_cache (description, raw_response) "
            "VALUES ('Beans; cooked', '{\"note\":\"a; b\"}'::jsonb);"
        ),
        "SELECT 1;",
    ]


def test_split_sql_statements_preserves_escaped_sql_quotes():
    statements = split_sql_statements("INSERT INTO foods VALUES ('Farmer''s; market');")

    assert statements == ["INSERT INTO foods VALUES ('Farmer''s; market');"]


@pytest.mark.asyncio
async def test_imported_food_cache_seed_exists_when_sentinel_is_present():
    connection = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = True
    connection.exec_driver_sql.return_value = result

    assert (
        await imported_food_cache_seed_exists(
            connection, "003_seed_nutrition_food_cache.sql"
        )
        is True
    )
    connection.exec_driver_sql.assert_awaited_once()
    assert (
        "provider_food_id = '170178'" in connection.exec_driver_sql.await_args.args[0]
    )


@pytest.mark.asyncio
async def test_imported_food_cache_seed_does_not_exist_without_sentinel():
    connection = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = False
    connection.exec_driver_sql.return_value = result

    assert (
        await imported_food_cache_seed_exists(
            connection, "003_seed_nutrition_food_cache.sql"
        )
        is False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("seed_name", "provider_food_id"),
    [
        ("004_seed_nutrition_food_cache.sql", "2705967"),
        ("005_seed_nutrition_food_cache.sql", "170007"),
    ],
)
async def test_later_imported_food_cache_seeds_use_their_own_sentinels(
    seed_name, provider_food_id
):
    connection = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = True
    connection.exec_driver_sql.return_value = result

    assert await imported_food_cache_seed_exists(connection, seed_name) is True
    assert (
        f"provider_food_id = '{provider_food_id}'"
        in connection.exec_driver_sql.await_args.args[0]
    )


@pytest.mark.asyncio
async def test_run_migrations_skips_imported_seed_before_reading_its_contents(
    monkeypatch, tmp_path
):
    migration_dir = tmp_path.parent / "db" / "migrations"
    migration_dir.mkdir(parents=True)
    seed = migration_dir / "005_seed_nutrition_food_cache.sql"
    seed.write_text("this is intentionally not valid SQL", encoding="utf-8")

    connection = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = True
    connection.exec_driver_sql.return_value = result

    class Transaction:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class Engine:
        def begin(self):
            return Transaction()

    monkeypatch.setattr(migrations, "Path", lambda _: tmp_path)

    await run_migrations(Engine())

    connection.exec_driver_sql.assert_awaited_once()
