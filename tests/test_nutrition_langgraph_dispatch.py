from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.config import get_settings
from app.services.agent_orchestrator import _nutrition_chat_context
from app.services.agent_service import build_api_graph, specialist_node_api


@pytest.mark.asyncio
async def test_nutrition_chat_context_combines_bounded_canonical_and_agent_data(
    monkeypatch,
):
    class Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_):
            return False

    main_service = Mock()
    main_service.list_meals = AsyncMock(
        return_value=[
            {
                "id": 4,
                "meal_type": "snack",
                "eaten_at": datetime(2026, 9, 24, 13, tzinfo=UTC),
                "untrusted_field": "do not expose",
                "items": [
                    {
                        "food_name": "Protein bar",
                        "quantity": 1,
                        "unit": "bar",
                        "calories": 200,
                        "protein_g": 20,
                        "untrusted_field": "do not expose",
                    }
                ],
            }
        ]
    )
    main_service.get_daily_summary = AsyncMock(
        return_value={
            "calories": 200,
            "protein_g": 20,
            "meal_count": 1,
            "remaining": {"calories": 2200, "protein_g": 140},
            "target": {"do_not_expose": True},
        }
    )
    agent_context = AsyncMock(
        return_value={
            "target_snapshot": {"calorie_target_kcal": 2400, "protein_target_g": 160},
            "meal_plan": {"id": 8, "status": "active", "private": "omit"},
        }
    )
    monkeypatch.setattr("app.db.database.AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr(
        "app.services.nutrition_service.NutritionService", lambda _: main_service
    )
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.nutrition_agent_client.get_nutrition_context",
        agent_context,
    )
    monkeypatch.setattr(
        "app.services.agent_orchestrator.datetime",
        Mock(now=Mock(return_value=datetime(2026, 9, 24, tzinfo=UTC))),
    )

    context = await _nutrition_chat_context(7)

    assert context == {
        "date": date(2026, 9, 24).isoformat(),
        "meal_logging": {
            "meal_count": 1,
            "meals": [
                {
                    "id": 4,
                    "meal_type": "snack",
                    "eaten_at": datetime(2026, 9, 24, 13, tzinfo=UTC),
                    "items": [
                        {
                            "food_name": "Protein bar",
                            "quantity": 1,
                            "unit": "bar",
                            "calories": 200,
                            "protein_g": 20,
                        }
                    ],
                }
            ],
        },
        "daily_summary": {
            "calories": 200,
            "protein_g": 20,
            "meal_count": 1,
            "remaining": {"calories": 2200, "protein_g": 140},
        },
        "active_target": {"calorie_target_kcal": 2400, "protein_target_g": 160},
        "active_meal_plan": {"id": 8, "status": "active"},
    }


@pytest.mark.asyncio
async def test_nutrition_chat_context_returns_partial_data_when_sources_fail(
    monkeypatch,
):
    class FailingSession:
        async def __aenter__(self):
            raise RuntimeError("main database offline")

        async def __aexit__(self, *_):
            return False

    monkeypatch.setattr("app.db.database.AsyncSessionLocal", lambda: FailingSession())
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.nutrition_agent_client.get_nutrition_context",
        AsyncMock(side_effect=RuntimeError("Nutrition Agent offline")),
    )

    context = await _nutrition_chat_context(7)

    assert context.keys() == {"date"}


def test_nutrition_specialist_uses_service_with_full_history(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "USE_NUTRITION_AGENT_SERVICE", True)
    respond = Mock(
        return_value={"message": "Eat a carb-and-protein meal within two hours."}
    )
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.nutrition_agent_client.respond", respond
    )
    state = {
        "next_agent": "nutrition_advisor",
        "volley_msg_left": 1,
        "user_profile": {"user_id": 7, "goal": "performance"},
        "messages": [
            {"role": "user", "content": "I ran 10 km."},
            {"role": "assistant", "content": "Nice work."},
            {"role": "user", "content": "What should I eat now?"},
        ],
    }

    result = specialist_node_api(state)

    respond.assert_called_once_with(
        user_id=7,
        messages=state["messages"],
        user_profile=state["user_profile"],
        nutrition_context={},
    )
    assert result["volley_msg_left"] == 0
    assert result["messages"][0]["name"] == "Sam (Nutrition Advisor)"
    assert "carb-and-protein" in result["messages"][0]["content"]


def test_compiled_langgraph_preserves_nutrition_context_for_specialist(monkeypatch):
    captured = {}

    def route_nutrition(state):
        return {
            "next_agent": "nutrition_advisor" if state["volley_msg_left"] > 0 else None
        }

    def nutrition_specialist(state):
        captured["nutrition_context"] = state["nutrition_context"]
        return {
            "messages": [
                {
                    "role": "assistant",
                    "name": "Sam (Nutrition Advisor)",
                    "content": "Sam (Nutrition Advisor): You logged a protein bar.",
                }
            ],
            "volley_msg_left": 0,
        }

    monkeypatch.setattr("agents.orchestrator", route_nutrition)
    monkeypatch.setattr(
        "app.services.agent_service.specialist_node_api", nutrition_specialist
    )

    nutrition_context = {
        "date": "2026-09-24",
        "meal_logging": {
            "meal_count": 1,
            "meals": [{"meal_type": "snack", "items": [{"food_name": "Protein bar"}]}],
        },
    }
    result = build_api_graph().invoke(
        {
            "messages": [
                {"role": "user", "content": "What meals have I logged today?"}
            ],
            "volley_msg_left": 1,
            "next_agent": None,
            "user_profile": {"user_id": 7},
            "nutrition_context": nutrition_context,
        }
    )

    assert captured["nutrition_context"] == nutrition_context
    assert result["messages"][-1]["content"].endswith("You logged a protein bar.")


def test_nutrition_service_failure_falls_back_to_local_specialist(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "USE_NUTRITION_AGENT_SERVICE", True)
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.nutrition_agent_client.respond",
        Mock(side_effect=RuntimeError("offline")),
    )
    local_specialist = Mock(
        return_value={
            "messages": [
                {
                    "role": "assistant",
                    "name": "Sam (Nutrition Advisor)",
                    "content": "Sam (Nutrition Advisor): Local fallback.",
                }
            ]
        }
    )
    monkeypatch.setattr("agents.specialist.specialist", local_specialist)
    state = {
        "next_agent": "nutrition_advisor",
        "volley_msg_left": 1,
        "user_profile": {"user_id": 7},
        "messages": [{"role": "user", "content": "What should I eat?"}],
    }

    result = specialist_node_api(state)

    local_specialist.assert_called_once_with("nutrition_advisor", state)
    assert result["volley_msg_left"] == 0
    assert result["messages"][0]["content"].endswith("Local fallback.")
