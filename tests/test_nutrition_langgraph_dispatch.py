from unittest.mock import Mock

from app.config import get_settings
from app.services.agent_service import specialist_node_api


def test_nutrition_specialist_uses_service_with_full_history(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "USE_NUTRITION_AGENT_SERVICE", True)
    respond = Mock(return_value={"message": "Eat a carb-and-protein meal within two hours."})
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
    )
    assert result["volley_msg_left"] == 0
    assert result["messages"][0]["name"] == "Sam (Nutrition Advisor)"
    assert "carb-and-protein" in result["messages"][0]["content"]


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