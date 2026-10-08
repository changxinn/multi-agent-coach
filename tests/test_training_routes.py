from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user
from app.api.routes.training import get_training_agent, router
from app.db.database import get_db
from app.services.training_agent_client import TrainingAgentUnavailableError


@pytest.fixture
def training_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    agent = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: {"id": 9, "role": "user"}
    app.dependency_overrides[get_training_agent] = lambda: agent
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    with TestClient(app) as client:
        yield client, agent


def test_preferences_are_scoped_to_authenticated_user(training_client):
    client, agent = training_client
    agent.preferences.return_value = {"equipment": ["dumbbells"]}

    response = client.post("/api/training/preferences/get", json={})

    assert response.status_code == 200
    agent.preferences.assert_awaited_once_with(9)


def test_workout_log_forwards_idempotency_key_and_never_accepts_user_id(
    training_client,
):
    client, agent = training_client
    agent.log_workout.return_value = {"id": 8, "reused": False}
    payload = {
        "occurred_at": "2026-10-07T12:00:00Z",
        "description": "Strength",
        "duration_minutes": 45,
        "session_rpe": 7,
        "exercise_performance": [],
    }

    response = client.post(
        "/api/training/workouts/log",
        json=payload,
        headers={"Idempotency-Key": "workout-1"},
    )

    assert response.status_code == 200
    assert agent.log_workout.await_args.args[0] == 9
    assert isinstance(agent.log_workout.await_args.args[1]["occurred_at"], datetime)
    assert agent.log_workout.await_args.args[2] == "workout-1"
    assert (
        client.post(
            "/api/training/workouts/log", json={**payload, "user_id": 3}
        ).status_code
        == 422
    )


def test_exercise_search_uses_authenticated_identity(training_client):
    client, agent = training_client
    agent.exercises_search.return_value = {"items": []}

    response = client.post("/api/training/exercises/search", json={"query": "squat"})

    assert response.status_code == 200
    agent.exercises_search.assert_awaited_once_with(9, "squat")


@pytest.mark.parametrize(
    ("path", "payload", "method"),
    [
        ("preferences/update", {"equipment": ["barbell"]}, "update_preferences"),
        ("exercises/lookup", {"query": "squat"}, "exercise_lookup"),
        ("programs/list", {}, "list_programs"),
        ("workouts/list", {}, "list_workouts"),
        ("progress", {}, "progress"),
    ],
)
def test_training_routes_forward_authenticated_data(
    training_client, path, payload, method
):
    client, agent = training_client
    getattr(agent, method).return_value = {"items": []}

    response = client.post(f"/api/training/{path}", json=payload)

    assert response.status_code == 200
    assert getattr(agent, method).await_count == 1


@pytest.mark.parametrize(
    ("path", "payload", "method"),
    [
        ("preferences/get", {}, "preferences"),
        ("preferences/update", {"equipment": []}, "update_preferences"),
        ("exercises/search", {"query": "squat"}, "exercises_search"),
        ("exercises/lookup", {"query": "squat"}, "exercise_lookup"),
        ("programs/list", {}, "list_programs"),
        (
            "workouts/log",
            {"occurred_at": "2026-01-01T00:00:00Z", "description": "lift"},
            "log_workout",
        ),
        ("workouts/list", {}, "list_workouts"),
        ("progress", {}, "progress"),
    ],
)
def test_training_routes_map_agent_unavailability_to_503(
    training_client, path, payload, method
):
    client, agent = training_client
    getattr(agent, method).side_effect = TrainingAgentUnavailableError("down")

    assert client.post(f"/api/training/{path}", json=payload).status_code == 503


def test_program_routes_forward_recovery_status_and_map_errors(
    training_client, monkeypatch
):
    client, agent = training_client
    monkeypatch.setattr(
        "app.api.routes.training.recovery_status", AsyncMock(return_value="amber")
    )
    agent.generate_program.return_value = {"id": 1}
    agent.adapt_program.return_value = {"id": 2}

    assert client.post("/api/training/programs/generate", json={}).status_code == 200
    assert (
        client.post(
            "/api/training/programs/adapt", json={"reason": "fatigue"}
        ).status_code
        == 200
    )
    agent.generate_program.assert_awaited_once_with(9, "amber")
    agent.adapt_program.assert_awaited_once_with(9, "fatigue", "amber")

    agent.generate_program.side_effect = TrainingAgentUnavailableError("down")
    agent.adapt_program.side_effect = TrainingAgentUnavailableError("down")
    assert client.post("/api/training/programs/generate", json={}).status_code == 503
    assert (
        client.post(
            "/api/training/programs/adapt", json={"reason": "fatigue"}
        ).status_code
        == 503
    )
