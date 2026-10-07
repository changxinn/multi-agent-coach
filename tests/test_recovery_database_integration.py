"""Live persistence/copy tests in temporary schemas on the private Recovery DB."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from services.recovery_agent.app.assessment import RecoveryHistory, assess_recovery
from services.recovery_agent.app.config import Settings
from services.recovery_agent.app.repository import RecoveryRepository
from services.recovery_agent.app.schemas import RecoveryEvaluateRequest, SleepLogCreate
from services.recovery_agent.migrate_legacy import copy_records

pytestmark = pytest.mark.integration


@pytest.fixture
async def recovery_repository():
    url = os.getenv("RECOVERY_INTEGRATION_DATABASE_URL")
    if not url:
        pytest.skip("RECOVERY_INTEGRATION_DATABASE_URL is required")
    schema = "recovery_test_" + uuid4().hex
    repo = RecoveryRepository(
        Settings(
            _env_file=None, RECOVERY_DATABASE_URL=url, RECOVERY_DATABASE_SCHEMA=schema
        )
    )
    # A configured but broken database must fail CI, not silently skip.
    await repo.connect()
    try:
        yield repo
    finally:
        await repo._pool.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await repo.close()


@pytest.mark.asyncio
async def test_private_database_lifecycle_without_main_users_table(recovery_repository):
    repo = recovery_repository
    user_id = 912345
    # No local users table exists and no connection to the main database is needed.
    assert (
        await repo._pool.fetchval(
            "SELECT to_regclass($1)", f"{repo.settings.DATABASE_SCHEMA}.users"
        )
        is None
    )
    created = await repo.create_sleep_log(
        SleepLogCreate(user_id=user_id, duration_minutes=300, quality=2)
    )
    await repo.write_record(
        "check-ins",
        {"user_id": user_id, "energy": 3, "soreness": 8, "stress": 7, "notes": None},
    )
    history = await repo.get_history(user_id)
    assert history.sleep_logs_last_7_days == 1
    assert history.average_sleep_minutes == 300
    result = assess_recovery(
        RecoveryEvaluateRequest(user_id=user_id, message="I feel tired"), history
    )
    await repo.save_assessment(user_id, result)
    records = await repo.list_records("assessments", 1, 10, user_id)
    assert isinstance(records["items"][0]["response"], dict)
    assert isinstance(records["items"][0]["tool_trace"], list)
    assert (await repo.list_records("sleep-logs", 1, 10, user_id + 1))["total"] == 0
    today = datetime.now(UTC).date()
    dashboard = await repo.dashboard_data(user_id, today, today)
    assert dashboard["latest_sleep"]["duration_minutes"] == 300
    assert len(dashboard["assessment_trend"]) == 1
    updated = await repo.write_record(
        "sleep-logs",
        {"user_id": user_id, "duration_minutes": 480, "quality": 4, "notes": "updated"},
        created["id"],
    )
    assert updated["duration_minutes"] == 480
    assert await repo.delete_record("sleep-logs", created["id"])
    assert not await repo.delete_record("sleep-logs", created["id"])


@pytest.mark.asyncio
async def test_copy_is_repeatable_preserves_ids_and_rolls_back_conflicts(
    recovery_repository,
):
    dest = recovery_repository
    source_schema = "recovery_legacy_test_" + uuid4().hex
    source_repo = RecoveryRepository(
        Settings(
            _env_file=None,
            RECOVERY_DATABASE_URL=dest.settings.DATABASE_URL,
            RECOVERY_DATABASE_SCHEMA=source_schema,
        )
    )
    await source_repo.connect()
    try:
        sleep = await source_repo.create_sleep_log(
            SleepLogCreate(user_id=42, duration_minutes=480, quality=4)
        )
        assessment = assess_recovery(
            RecoveryEvaluateRequest(user_id=42, message="I slept well"),
            RecoveryHistory(),
        )
        await source_repo.save_assessment(42, assessment)
        async with (
            source_repo._pool.acquire() as source,
            dest._pool.acquire() as target,
        ):
            counts = await copy_records(
                source, target, source_schema, dest.settings.DATABASE_SCHEMA
            )
            assert counts["sleep_logs"] == 1
            assert counts["recovery_assessments"] == 1
            assert all(
                count == 0
                for count in (
                    await copy_records(
                        source, target, source_schema, dest.settings.DATABASE_SCHEMA
                    )
                ).values()
            )
        copied = (await dest.list_records("sleep-logs", 1, 10, 42))["items"][0]
        assert copied["id"] == sleep["id"]
        assert copied["created_at"] == sleep["created_at"]
        new = await dest.create_sleep_log(
            SleepLogCreate(user_id=42, duration_minutes=420, quality=3)
        )
        assert new["id"] > copied["id"]
        # The next source ID clashes with a different destination record.
        await source_repo.create_sleep_log(
            SleepLogCreate(user_id=42, duration_minutes=360, quality=2)
        )
        async with (
            source_repo._pool.acquire() as source,
            dest._pool.acquire() as target,
        ):
            with pytest.raises(RuntimeError, match="Conflicting"):
                await copy_records(
                    source, target, source_schema, dest.settings.DATABASE_SCHEMA
                )
        assert (await dest.list_records("sleep-logs", 1, 10, 42))["total"] == 2
        assert (await source_repo.list_records("sleep-logs", 1, 10, 42))["total"] == 2
    finally:
        await source_repo._pool.execute(f'DROP SCHEMA "{source_schema}" CASCADE')
        await source_repo.close()


@pytest.mark.asyncio
async def test_copy_rolls_back_earlier_table_inserts_on_later_conflict(
    recovery_repository,
):
    dest = recovery_repository
    source_schema = "recovery_legacy_test_" + uuid4().hex
    source_repo = RecoveryRepository(
        Settings(
            _env_file=None,
            RECOVERY_DATABASE_URL=dest.settings.DATABASE_URL,
            RECOVERY_DATABASE_SCHEMA=source_schema,
        )
    )
    await source_repo.connect()
    try:
        await source_repo.create_sleep_log(
            SleepLogCreate(user_id=42, duration_minutes=480, quality=4)
        )
        values = {"user_id": 42, "energy": 8, "soreness": 2, "stress": 3, "notes": None}
        await source_repo.write_record("check-ins", values)
        await dest.write_record("check-ins", {**values, "energy": 1})
        async with (
            source_repo._pool.acquire() as source,
            dest._pool.acquire() as target,
        ):
            with pytest.raises(RuntimeError, match="Conflicting recovery_checkins"):
                await copy_records(
                    source, target, source_schema, dest.settings.DATABASE_SCHEMA
                )
        assert (await dest.list_records("sleep-logs", 1, 10, 42))["total"] == 0
        assert (await dest.list_records("check-ins", 1, 10, 42))["items"][0][
            "energy"
        ] == 1
        assert (await source_repo.list_records("sleep-logs", 1, 10, 42))["total"] == 1
    finally:
        await source_repo._pool.execute(f'DROP SCHEMA "{source_schema}" CASCADE')
        await source_repo.close()
