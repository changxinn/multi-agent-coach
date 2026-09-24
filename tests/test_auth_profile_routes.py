from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user, router
from app.db.database import get_db


@pytest.fixture
def auth_profile_client(monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 9,
        "email": "member@example.com",
        "name": "Member",
        "role": "user",
    }
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    service = AsyncMock()
    monkeypatch.setattr("app.api.routes.auth.UserProfileService", lambda db: service)
    with TestClient(app) as client:
        yield client, service


def test_get_profile_returns_only_authenticated_users_profile(auth_profile_client):
    client, service = auth_profile_client
    service.get_user_profile.return_value = {
        "user_id": 9,
        "fitness_goal": "general fitness",
        "fitness_level": "beginner",
        "weight_kg": 70.5,
        "height_cm": 175.0,
        "age": 30,
    }

    response = client.get("/api/auth/profile")

    assert response.status_code == 200
    assert response.json()["email"] == "member@example.com"
    assert response.json()["fitness_profile"]["weight_kg"] == 70.5
    service.get_user_profile.assert_awaited_once_with(9)


def test_update_profile_scopes_update_to_authenticated_user(auth_profile_client):
    client, service = auth_profile_client
    service.update_fitness_profile.return_value = {
        "user_id": 9,
        "fitness_goal": "general fitness",
        "fitness_level": "beginner",
        "weight_kg": 72.25,
        "height_cm": 180.5,
        "age": 31,
    }

    response = client.put(
        "/api/auth/profile",
        json={"age": 31, "weight_kg": 72.25, "height_cm": 180.5},
    )

    assert response.status_code == 200
    assert response.json()["fitness_profile"]["age"] == 31
    service.update_fitness_profile.assert_awaited_once_with(
        9, age=31, weight_kg=72.25, height_cm=180.5
    )


def test_update_profile_rejects_invalid_measurements(auth_profile_client):
    client, service = auth_profile_client

    response = client.put("/api/auth/profile", json={"age": 0})

    assert response.status_code == 422
    service.update_fitness_profile.assert_not_awaited()
