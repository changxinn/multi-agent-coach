from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.training_agent.app import main


def test_training_api_routes_require_token_and_delegate(monkeypatch):
    monkeypatch.setattr(main.settings, "RUN_MIGRATIONS", False)
    monkeypatch.setattr(main.settings, "INTERNAL_SERVICE_TOKEN", "token")
    service = AsyncMock()
    service.exercise_guidance.return_value = [{"name": "squat", "guidance": "Brace."}]
    service.exercises.side_effect = [
        [{"name": "squat", "guidance": "Brace."}],
        [],
        [{"name": "squat", "guidance": "Brace."}],
        [],
    ]
    service.generate_program.return_value = {"id": 1}
    service.list_programs.return_value = []
    service.log_workout.return_value = {"id": 1}
    service.list_workouts.return_value = []
    service.progress.return_value = {"workout_count": 0}
    service.daily_workout.return_value = {"status": "ready"}
    service.profile.return_value = {"fitness_goal": "strength"}
    service.save_profile.return_value = {"fitness_goal": "strength"}
    service.preferences.return_value = {"equipment": []}
    service.save_preferences.return_value = {"equipment": []}
    service.context.return_value = {"profile": {}}
    main.app.dependency_overrides[main.get_service] = lambda: service

    headers = {"X-Internal-Service-Token": "token"}
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert (
            client.post("/v1/training/progress", json={"user_id": 1}).status_code == 401
        )
        assert (
            client.post(
                "/v1/training/exercises/search",
                headers=headers,
                json={"user_id": 1, "query": "squat"},
            ).json()["items"][0]["name"]
            == "squat"
        )
        assert (
            client.post(
                "/v1/training/exercises/lookup",
                headers=headers,
                json={"user_id": 1, "query": "squat"},
            ).json()["name"]
            == "squat"
        )
        assert (
            client.post(
                "/v1/training/exercises/lookup",
                headers=headers,
                json={"user_id": 1, "query": "unknown"},
            ).json()["name"]
            == "unknown"
        )
        assert (
            client.post(
                "/v1/training/programs/generate", headers=headers, json={"user_id": 1}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/programs/list", headers=headers, json={"user_id": 1}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/programs/adapt",
                headers=headers,
                json={"user_id": 1, "reason": "tired"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/workouts/log",
                headers=headers,
                json={
                    "user_id": 1,
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "description": "lift",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/workouts/list", headers=headers, json={"user_id": 1}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/progress", headers=headers, json={"user_id": 1}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/daily-workout",
                headers=headers,
                json={"user_id": 1, "date": "2026-01-01"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/profile/get", headers=headers, json={"user_id": 1}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/profile/update",
                headers=headers,
                json={"user_id": 1, "fitness_goal": "strength"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/preferences/get", headers=headers, json={"user_id": 1}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/preferences/update",
                headers=headers,
                json={"user_id": 1, "equipment": ["barbell"]},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/training/context", headers=headers, json={"user_id": 1}
            ).status_code
            == 200
        )
        assert client.post(
            "/v1/training/chat",
            headers=headers,
            json={"user_id": 1, "messages": [{"role": "user", "content": "squat"}]},
        ).json()["tool_trace"] == ["exercise_lookup"]
        assert (
            client.post(
                "/v1/training/chat",
                headers=headers,
                json={"user_id": 1, "messages": [{"role": "user", "content": "help"}]},
            ).json()["tool_trace"]
            == []
        )
    main.app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_training_agent_lifecycle_and_validation_errors(monkeypatch):
    monkeypatch.setattr(main.settings, "RUN_MIGRATIONS", True)
    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(main, "close_db", AsyncMock())
    await main.startup()
    await main.shutdown()
    main.init_db.assert_awaited_once()
    main.close_db.assert_awaited_once()

    monkeypatch.setattr(main.settings, "RUN_MIGRATIONS", False)
    main.init_db.reset_mock()
    await main.startup()
    main.init_db.assert_not_awaited()


def test_private_api_maps_service_validation_errors(monkeypatch):
    monkeypatch.setattr(main.settings, "RUN_MIGRATIONS", False)
    monkeypatch.setattr(main.settings, "INTERNAL_SERVICE_TOKEN", "token")
    service = AsyncMock()
    service.generate_program.side_effect = ValueError("blocked")
    service.log_workout.side_effect = ValueError("missing key")
    main.app.dependency_overrides[main.get_service] = lambda: service
    headers = {"X-Internal-Service-Token": "token"}
    with TestClient(main.app) as client:
        assert (
            client.post(
                "/v1/training/programs/generate", headers=headers, json={"user_id": 1}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/training/workouts/log",
                headers=headers,
                json={
                    "user_id": 1,
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "description": "lift",
                },
            ).status_code
            == 422
        )
    main.app.dependency_overrides.clear()
