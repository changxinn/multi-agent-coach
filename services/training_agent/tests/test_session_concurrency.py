import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import InvalidRequestError

from services.training_agent.app import database, main
from services.training_agent.app.service import TrainingService


class GuardedSession:
    """Yield during queries, rejecting concurrent use like an AsyncSession."""

    def __init__(self, fail_at=None):
        self.active = False
        self.closed = False
        self.queries = []
        self.fail_at = fail_at
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        assert not self.active, "Session closed while a query was still running"
        self.closed = True

    async def execute(self, statement, params):
        assert not self.closed
        if self.active:
            raise InvalidRequestError("Concurrent operations are not permitted")
        self.active = True
        sql = str(statement)
        self.queries.append(sql)
        try:
            await asyncio.sleep(0)
            if len(self.queries) == self.fail_at:
                raise RuntimeError("Query failed")
            result = Mock()
            mappings = result.mappings.return_value
            if "athlete_training_profiles" in sql:
                mappings.first.return_value = {"fitness_goal": "strength"}
            elif "FROM training_preferences" in sql:
                mappings.first.return_value = {"equipment": ["dumbbells"]}
            elif "COUNT(*)" in sql:
                mappings.one.return_value = {"workout_count": 0, "average_rpe": None}
            elif "FROM workout_logs" in sql:
                result.mappings.return_value = []
            elif "FROM exercises" in sql:
                result.mappings.return_value = [
                    {"name": "squat", "guidance": "Brace and stop for pain."}
                ]
            elif "MAX(version)" in sql:
                result.scalar_one.return_value = 0
            elif "INSERT INTO training_programs" in sql:
                mappings.one.return_value = {
                    "id": 1,
                    "version": params["version"],
                    "created_at": "2026-10-01T00:00:00Z",
                }
            elif "INSERT INTO training_adaptations" not in sql:
                raise AssertionError(f"Unexpected query: {sql}")
            return result
        finally:
            self.active = False


@pytest.fixture
def request_sessions(monkeypatch):
    sessions = []

    def factory():
        session = GuardedSession()
        sessions.append(session)
        return session

    monkeypatch.setattr(database, "session_factory", lambda: factory)
    monkeypatch.setattr(main.settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    monkeypatch.setattr(
        TrainingService,
        "_llm_json",
        staticmethod(lambda *_: {"days": [{"day": "Day 1"}], "target_rpe": "7"}),
    )
    return sessions


@pytest.mark.asyncio
async def test_context_queries_are_sequential_and_preserve_response():
    session = GuardedSession()
    context = await TrainingService(session).context(1)
    assert context == {
        "profile": {"fitness_goal": "strength"},
        "preferences": {"equipment": ["dumbbells"]},
        "progress_summary": {
            "workout_count": 0,
            "average_rpe": None,
            "plateau_detected": False,
        },
        "recent_workouts": [],
    }
    assert len(session.queries) == 4
    assert not session.active


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_at", [1, 2, 3, 4])
async def test_context_failure_leaves_no_queries_running(fail_at):
    session = GuardedSession(fail_at=fail_at)
    async with session:
        with pytest.raises(RuntimeError, match="Query failed"):
            await TrainingService(session).context(1)
        assert len(session.queries) == fail_at
        assert not session.active
    assert session.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("program_endpoint", ["generate", "adapt"])
async def test_both_tabs_concurrently_use_independent_request_sessions(
    request_sessions, program_endpoint
):
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://training"
    ) as client:
        payload = {"user_id": 1, "recovery_status": "green"}
        if program_endpoint == "adapt":
            payload["reason"] = "fatigue"
        guidance, program = await asyncio.gather(
            client.post(
                "/v1/training/exercises/search",
                headers={"X-Internal-Service-Token": "test-token"},
                json={"user_id": 1, "query": "squat"},
            ),
            client.post(
                f"/v1/training/programs/{program_endpoint}",
                headers={"X-Internal-Service-Token": "test-token"},
                json=payload,
            ),
        )
    assert guidance.status_code == 200
    assert guidance.json()["items"][0]["name"] == "squat"
    assert program.status_code == 200
    assert program.json()["goal"] == "strength"
    assert program.json()["generation_source"] == "llm"
    assert len(request_sessions) == 2
    for session in request_sessions:
        assert session.closed
        assert not session.active
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
