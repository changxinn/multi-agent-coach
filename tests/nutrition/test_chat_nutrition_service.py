"""Nutrition Agent chat-routing safety coverage."""

from __future__ import annotations

import importlib

import pytest

from app.services import agent_service
from app.services.nutrition_agent_client import NutritionAgentError

specialist_module = importlib.import_module("agents.specialist")


def _state(profile: object) -> dict:
    return {
        "next_agent": "nutrition_advisor",
        "volley_msg_left": 2,
        "messages": [{"role": "user", "content": "You: I need nutrition guidance."}],
        "user_profile": profile,
    }


@pytest.mark.asyncio
async def test_chat_uses_service_with_valid_user_and_preserves_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, str, dict[str, object] | None]] = []

    async def get_profile(_: int) -> dict[str, object]:
        return {"timezone": "America/New_York", "dietary_preference": "vegetarian", "dietary_restrictions": [], "allergies": ["peanut"], "meals_per_day": 3, "activity_level": "moderate", "age": 30, "gender": "female", "weight_kg": 65, "height_cm": 165, "ignored": "never forwarded"}

    async def evaluate(user_id: int, message: str, **kwargs: object) -> dict:
        calls.append((user_id, message, kwargs.get("profile")))
        return {
            "message": "Please seek qualified healthcare support.",
            "status": "escalate",
            "score": 10,
            "safety_findings": [{"code": "DIABETES_OR_INSULIN", "severity": "escalate"}],
            "escalation": {"message": "Please seek qualified healthcare support.", "urgent": False},
        }

    monkeypatch.setattr(specialist_module, "specialist", lambda *_: pytest.fail("local fallback"))
    monkeypatch.setattr("app.services.nutrition_agent_client.nutrition_agent_client.evaluate", evaluate)
    monkeypatch.setattr("app.services.nutrition_agent_client.nutrition_agent_client.get_profile", get_profile)
    monkeypatch.setattr(
        "app.services.nutrition_rollout.is_nutrition_agent_enabled_for_user", lambda *_: True
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: type("Settings", (), {"USE_NUTRITION_AGENT_SERVICE": True, "NUTRITION_AGENT_ROLLOUT_PERCENT": 100})(),
    )

    result = await agent_service.specialist_node_api(_state({"user_id": 42}))

    assert calls == [(42, "I need nutrition guidance.", {"timezone": "America/New_York", "dietary_preference": "vegetarian", "dietary_restrictions": [], "allergies": ["peanut"], "meals_per_day": 3, "activity_level": "moderate", "age": 30, "gender": "female", "weight_kg": 65.0, "height_cm": 165.0})]
    metadata = result["messages"][0]["metadata"]
    assert metadata["nutrition_status"] == "escalate"
    assert metadata["safety_findings"] == [
        {"code": "DIABETES_OR_INSULIN", "severity": "escalate"}
    ]
    assert metadata["escalation"] == {
        "message": "Please seek qualified healthcare support.",
        "urgent": False,
    }


@pytest.mark.asyncio
async def test_chat_missing_user_id_uses_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    fallback = {"messages": [{"role": "assistant", "content": "Local response"}]}

    monkeypatch.setattr(specialist_module, "specialist", lambda *_: fallback)
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: type("Settings", (), {"USE_NUTRITION_AGENT_SERVICE": True, "NUTRITION_AGENT_ROLLOUT_PERCENT": 100})(),
    )

    result = await agent_service.specialist_node_api(_state({}))

    assert result["messages"] == fallback["messages"]
    assert result["volley_msg_left"] == 1

@pytest.mark.asyncio
async def test_chat_missing_nutrition_profile_returns_onboarding_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_profile(_: int) -> object:
        raise NutritionAgentError(404, "NUTRITION_PROFILE_NOT_FOUND")

    monkeypatch.setattr(specialist_module, "specialist", lambda *_: pytest.fail("local fallback"))
    monkeypatch.setattr("app.services.nutrition_agent_client.nutrition_agent_client.get_profile", get_profile)
    monkeypatch.setattr("app.services.nutrition_agent_client.nutrition_agent_client.evaluate", lambda *_: pytest.fail("evaluation"))
    monkeypatch.setattr("app.services.nutrition_rollout.is_nutrition_agent_enabled_for_user", lambda *_: True)
    monkeypatch.setattr("app.config.get_settings", lambda: type("Settings", (), {"USE_NUTRITION_AGENT_SERVICE": True, "NUTRITION_AGENT_ROLLOUT_PERCENT": 100})())

    result = await agent_service.specialist_node_api(_state({"user_id": 42}))

    assert result["volley_msg_left"] == 1
    response = result["messages"][0]
    assert response["name"] == "Sam (Nutrition Advisor)"
    assert "Asia/Singapore" in response["content"]
    assert response["metadata"] == {
        "nutrition_status": "profile_required",
        "nutrition_profile_required": True,
    }


@pytest.mark.asyncio
async def test_chat_invalid_nutrition_profile_uses_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    fallback = {"messages": [{"role": "assistant", "content": "Local response"}]}

    async def get_profile(_: int) -> object:
        return {"dietary_preference": "unverified"}

    monkeypatch.setattr(specialist_module, "specialist", lambda *_: fallback)
    monkeypatch.setattr("app.services.nutrition_agent_client.nutrition_agent_client.get_profile", get_profile)
    monkeypatch.setattr("app.services.nutrition_agent_client.nutrition_agent_client.evaluate", lambda *_: pytest.fail("evaluation"))
    monkeypatch.setattr("app.services.nutrition_rollout.is_nutrition_agent_enabled_for_user", lambda *_: True)
    monkeypatch.setattr("app.config.get_settings", lambda: type("Settings", (), {"USE_NUTRITION_AGENT_SERVICE": True, "NUTRITION_AGENT_ROLLOUT_PERCENT": 100})())

    assert (await agent_service.specialist_node_api(_state({"user_id": 42})))["messages"] == fallback["messages"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["profile", "evaluate"])
async def test_chat_nutrition_dependency_failure_uses_local_fallback(monkeypatch: pytest.MonkeyPatch, failure_stage: str) -> None:
    fallback = {"messages": [{"role": "assistant", "content": "Local response"}]}

    async def profile(_: int) -> dict[str, object]:
        if failure_stage == "profile":
            raise NutritionAgentError(503)
        return {"dietary_preference": "omnivore", "dietary_restrictions": [], "allergies": [], "meals_per_day": 3, "activity_level": "moderate", "age": None, "gender": None, "weight_kg": None, "height_cm": None}

    async def unavailable(*_: object, **__: object) -> object:
        raise NutritionAgentError(503)

    monkeypatch.setattr(specialist_module, "specialist", lambda *_: fallback)
    monkeypatch.setattr("app.services.nutrition_agent_client.nutrition_agent_client.get_profile", profile)
    monkeypatch.setattr("app.services.nutrition_agent_client.nutrition_agent_client.evaluate", unavailable)
    monkeypatch.setattr("app.services.nutrition_rollout.is_nutrition_agent_enabled_for_user", lambda *_: True)
    monkeypatch.setattr("app.config.get_settings", lambda: type("Settings", (), {"USE_NUTRITION_AGENT_SERVICE": True, "NUTRITION_AGENT_ROLLOUT_PERCENT": 100})())

    assert (await agent_service.specialist_node_api(_state({"user_id": 42})))["messages"] == fallback["messages"]
