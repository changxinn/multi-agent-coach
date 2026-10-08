from unittest.mock import Mock

from app.config import get_settings
from app.services.agent_service import specialist_node_api


def test_training_specialist_uses_service_and_preserves_alex_identity(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    settings = get_settings()
    monkeypatch.setattr(settings, "USE_TRAINING_AGENT_SERVICE", True)
    respond = Mock(
        return_value={
            "message": "Use a controlled squat range.",
            "tool_trace": ["exercise_lookup"],
        }
    )
    monkeypatch.setattr(
        "app.services.training_agent_client.training_agent_client.respond", respond
    )
    state = {
        "next_agent": "training_planner",
        "volley_msg_left": 1,
        "user_profile": {"user_id": 7},
        "messages": [{"role": "user", "content": "How do I squat?"}],
    }

    result = specialist_node_api(state)

    respond.assert_called_once_with(
        user_id=7, messages=state["messages"], user_profile=state["user_profile"]
    )
    assert result["messages"][0]["name"] == "Alex (Training Planner)"
    assert result["messages"][0]["metadata"]["tool_trace"] == ["exercise_lookup"]


def test_training_specialist_falls_back_locally_when_service_fails(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "USE_TRAINING_AGENT_SERVICE", True)
    monkeypatch.setattr(
        "app.services.training_agent_client.training_agent_client.respond",
        Mock(side_effect=RuntimeError("down")),
    )
    local = Mock(return_value={"messages": [{"role": "assistant", "content": "Local"}]})
    monkeypatch.setattr("agents.specialist.specialist", local)
    state = {"next_agent": "training_planner", "volley_msg_left": 1, "messages": []}

    result = specialist_node_api(state)

    local.assert_called_once_with("training_planner", state)
    assert result["volley_msg_left"] == 0
