"""Regression coverage for dietary preference declarations in chat."""

from __future__ import annotations

import pytest

from app.services import agent_service


def _state(message: str) -> dict:
    return {
        "next_agent": "nutrition_advisor",
        "volley_msg_left": 2,
        "messages": [{"role": "user", "content": f"You: {message}"}],
        "user_profile": {"user_id": 42},
    }


def _nutrition_profile() -> dict[str, object]:
    return {
        "timezone": "America/New_York",
        "dietary_preference": "omnivore",
        "dietary_restrictions": ["low sodium"],
        "allergies": ["peanut"],
        "meals_per_day": 3,
        "activity_level": "moderate",
        "age": 30,
        "gender": "female",
        "weight_kg": 65,
        "height_cm": 165,
    }


@pytest.mark.asyncio
async def test_chat_preference_declaration_updates_profile_without_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[tuple[int, dict[str, object]]] = []

    async def get_profile(_: int) -> dict[str, object]:
        return _nutrition_profile()

    async def upsert_profile(user_id: int, payload: dict[str, object]) -> dict[str, object]:
        saved.append((user_id, payload))
        return payload

    monkeypatch.setattr(
        "app.services.nutrition_agent_client.nutrition_agent_client.get_profile",
        get_profile,
    )
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.nutrition_agent_client.upsert_profile",
        upsert_profile,
    )
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.nutrition_agent_client.evaluate",
        lambda *_args, **_kwargs: pytest.fail("preference-only input must not be evaluated"),
    )
    monkeypatch.setattr(
        "app.services.nutrition_rollout.is_nutrition_agent_enabled_for_user", lambda *_: True,
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: type("Settings", (), {"USE_NUTRITION_AGENT_SERVICE": True, "NUTRITION_AGENT_ROLLOUT_PERCENT": 100})(),
    )

    result = await agent_service.specialist_node_api(_state("I am a vegetarian."))

    assert saved == [(42, {**_nutrition_profile(), "dietary_preference": "vegetarian"})]
    message = result["messages"][0]
    assert message["content"] == (
        "Sam (Nutrition Advisor): Got it—I’ve updated your dietary preference to vegetarian. "
        "What meal or nutrition goal would you like help with?"
    )
    assert message["metadata"] == {
        "nutrition_profile_updated": True,
        "dietary_preference": "vegetarian",
    }


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("I am a vegetarian.", "vegetarian"),
        ("I'm a vegan", "vegan"),
        ("I am a pescatarian!", "pescatarian"),
        ("Make me an omnivore.", "omnivore"),
        ("Give me a vegetarian dinner.", None),
    ],
)
def test_declared_dietary_preference_requires_a_preference_only_statement(
    message: str, expected: str | None,
) -> None:
    assert agent_service._declared_dietary_preference(message) == expected


def test_preference_declaration_routes_to_nutrition_without_llm() -> None:
    from agents.orchestrator import _deterministic_specialist

    assert _deterministic_specialist(
        [{"role": "user", "content": "You: I am a vegetarian."}]
    ) == "nutrition_advisor"