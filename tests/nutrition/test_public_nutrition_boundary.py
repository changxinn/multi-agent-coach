"""Public Nutrition request-ID, error-envelope, and typed-response coverage."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.api.routes.auth import get_current_user
from app.main import app
from app.services.nutrition_agent_client import (
    NutritionAgentError,
    nutrition_agent_client,
)


@pytest.fixture
def public_app():
    app.dependency_overrides[get_current_user] = lambda: {"id": 42}
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_food_validation_uses_canonical_envelope_and_generated_request_id(
    public_app: FastAPI,
) -> None:
    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/nutrition/foods", params={"q": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_food_dependency_error_preserves_caller_request_id(
    monkeypatch: pytest.MonkeyPatch, public_app: FastAPI
) -> None:
    async def unavailable(*_: object, **__: object) -> None:
        raise NutritionAgentError()

    monkeypatch.setattr(nutrition_agent_client, "request", unavailable)
    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/nutrition/foods",
            params={"q": "oats"},
            headers={"X-Request-ID": "request-42"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DEPENDENCY_UNAVAILABLE",
            "message": "Nutrition service is temporarily unavailable.",
            "request_id": "request-42",
        }
    }
    assert response.headers["X-Request-ID"] == "request-42"


@pytest.mark.asyncio
async def test_safety_referral_is_forwarded_in_the_canonical_envelope(
    monkeypatch: pytest.MonkeyPatch, public_app: FastAPI
) -> None:
    async def referral(*_: object, **__: object) -> None:
        raise NutritionAgentError(
            422,
            "NUTRITION_SAFETY_REFERRAL_REQUIRED",
            "Please seek qualified healthcare support.",
        )

    monkeypatch.setattr(nutrition_agent_client, "request", referral)
    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/nutrition/targets/calculate",
            json={
                "inputs": {
                    "age": 30,
                    "gender": "female",
                    "weight_kg": 65,
                    "height_cm": 165,
                    "activity_level": "moderate",
                    "fitness_goal": "maintenance",
                }
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NUTRITION_SAFETY_REFERRAL_REQUIRED"
    assert response.json()["error"]["message"] == "Please seek qualified healthcare support."


@pytest.mark.asyncio
async def test_invalid_public_meal_payload_is_rejected_before_private_client(
    monkeypatch: pytest.MonkeyPatch, public_app: FastAPI
) -> None:
    called = False

    async def unexpected(*_: object, **__: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(nutrition_agent_client, "request_for_user", unexpected)
    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/nutrition/meal-logs",
            json={"meal_type": "lunch", "description": "  ", "unexpected": True},
            headers={"X-Request-ID": "invalid-meal-42"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "request_id": "invalid-meal-42",
        }
    }
    assert not called


@pytest.mark.asyncio
async def test_private_profile_validation_message_is_actionable(
    monkeypatch: pytest.MonkeyPatch, public_app: FastAPI
) -> None:
    async def invalid_profile(*_: object, **__: object) -> None:
        raise NutritionAgentError(
            422,
            "VALIDATION_ERROR",
            "Timezone must be a valid IANA timezone",
        )

    monkeypatch.setattr(nutrition_agent_client, "request_for_user", invalid_profile)
    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/nutrition/profile",
            json={"timezone": "Asia/Singapore"},
            headers={"X-Request-ID": "invalid-profile-42"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Timezone must be a valid IANA timezone",
            "request_id": "invalid-profile-42",
        }
    }


@pytest.mark.asyncio
async def test_downstream_resource_and_value_codes_are_preserved(
    monkeypatch: pytest.MonkeyPatch, public_app: FastAPI
) -> None:
    async def missing(*_: object, **__: object) -> None:
        raise NutritionAgentError(404, "MEAL_LOG_NOT_FOUND")

    monkeypatch.setattr(nutrition_agent_client, "request_for_user", missing)
    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        missing_response = await client.get("/api/nutrition/meal-logs/8")

    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "MEAL_LOG_NOT_FOUND"
    assert missing_response.json()["error"]["message"] == "The requested nutrition resource was not found."

    async def inconsistent(*_: object, **__: object) -> None:
        raise NutritionAgentError(422, "NUTRITION_VALUE_INCONSISTENT", "private detail")

    monkeypatch.setattr(nutrition_agent_client, "request_for_user", inconsistent)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        inconsistent_response = await client.post(
            "/api/nutrition/targets/calculate",
            json={
                "inputs": {
                    "age": 30,
                    "gender": "female",
                    "weight_kg": 65,
                    "height_cm": 165,
                    "activity_level": "moderate",
                    "fitness_goal": "maintenance",
                }
            },
        )

    assert inconsistent_response.status_code == 422
    assert inconsistent_response.json()["error"] == {
        "code": "NUTRITION_VALUE_INCONSISTENT",
        "message": "Nutrition values are inconsistent.",
        "request_id": inconsistent_response.headers["X-Request-ID"],
    }


@pytest.mark.asyncio
async def test_client_forwards_request_id_to_private_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request_id"] = request.headers["X-Request-ID"]
        return httpx.Response(
            200,
            json={
                "items": [],
                "source": "cache_only",
                "upstream_status": "not_requested",
                "stale": False,
            },
        )

    client = nutrition_agent_client
    original_client = client._client
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "NUTRITION_INTERNAL_SERVICE_TOKEN": "internal-token",
                "NUTRITION_AGENT_URL": "http://nutrition-agent",
            },
        )(),
    )
    transport = httpx.ASGITransport(app=app)
    app.dependency_overrides[get_current_user] = lambda: {"id": 42}
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as public_client:
            await public_client.get(
                "/api/nutrition/foods",
                params={"q": "oats"},
                headers={"X-Request-ID": "request-42"},
            )
    finally:
        app.dependency_overrides.clear()
        await client.close()
        client._client = original_client

    assert captured["request_id"] == "request-42"


@pytest.mark.asyncio
async def test_client_forwards_explicit_safety_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def request(*_: object, **kwargs: object) -> dict:
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(nutrition_agent_client, "request", request)

    await nutrition_agent_client.evaluate(
        42,
        "Need nutrition guidance.",
        safety_context={"risk_flags": ["under_18"]},
    )

    assert captured["json"] == {
        "message": "Need nutrition guidance.",
        "safety_context": {"risk_flags": ["under_18"]},
    }
