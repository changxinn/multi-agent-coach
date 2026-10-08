from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user
from app.api.routes.training import get_training_agent, router


@pytest.fixture
def training_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    agent = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: {"id": 9, "role": "user"}
    app.dependency_overrides[get_training_agent] = lambda: agent
    with TestClient(app) as client:
        yield client, agent


def test_preferences_are_scoped_to_authenticated_user(training_client):
    client, agent = training_client
    agent.preferences.return_value = {"equipment": ["dumbbells"]}

    response = client.post("/api/training/preferences/get", json={})

    assert response.status_code == 200
    agent.preferences.assert_awaited_once_with(9)


def test_workout_log_forwards_idempotency_key_and_never_accepts_user_id(training_client):
    client, agent = training_client
    agent.log_workout.return_value = {"id": 8, "reused": False}
    payload = {"occurred_at": "2026-10-07T12:00:00Z", "description": "Strength", "duration_minutes": 45, "session_rpe": 7, "exercise_performance": []}

    response = client.post("/api/training/workouts/log", json=payload, headers={"Idempotency-Key": "workout-1"})

    assert response.status_code == 200
    assert agent.log_workout.await_args.args[0] == 9
    assert isinstance(agent.log_workout.await_args.args[1]["occurred_at"], datetime)
    assert agent.log_workout.await_args.args[2] == "workout-1"
    assert client.post("/api/training/workouts/log", json={**payload, "user_id": 3}).status_code == 422


def test_exercise_search_uses_authenticated_identity(training_client):
    client, agent = training_client
    agent.exercises_search.return_value = {"items": []}

    response = client.post("/api/training/exercises/search", json={"query": "squat"})

    assert response.status_code == 200
    agent.exercises_search.assert_awaited_once_with(9, "squat")