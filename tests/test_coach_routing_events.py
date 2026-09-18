import os

import pytest

from agents.head_coach_client import HeadCoachClient
from agents.orchestrator import route_locally
from app.services.coach_event_store import resolve_persisted_routing_agent


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("USE_HEAD_COACH_SERVICE", raising=False)


def test_persisted_agent_prefers_specialist_after_turn_returns_to_user():
    assert (
        resolve_persisted_routing_agent(
            {
                "next_agent": "human",
                "selected_agent": "training_planner",
                "routing_reason": "LLM selected a specialist for the latest message.",
            }
        )
        == "training_planner"
    )


def test_persisted_agent_stays_human_when_head_coach_kept_the_turn():
    assert (
        resolve_persisted_routing_agent(
            {"next_agent": "human", "selected_agent": "human"}
        )
        == "human"
    )


def test_route_locally_records_selected_specialist():
    result = route_locally(
        {
            "volley_msg_left": 1,
            "user_profile": {"goal": "Hyrox", "fitness_level": "beginner"},
            "messages": [
                {"role": "user", "content": "You: Plan a gym workout with squats"}
            ],
        }
    )
    assert result["next_agent"] == "training_planner"
    assert result["selected_agent"] == "training_planner"


def test_route_locally_volley_end_does_not_overwrite_selected_agent():
    result = route_locally(
        {
            "volley_msg_left": 0,
            "selected_agent": "nutrition_advisor",
            "next_agent": "nutrition_advisor",
            "messages": [{"role": "user", "content": "You: What should I eat?"}],
        }
    )
    assert result["next_agent"] == "human"
    assert "selected_agent" not in result
    assert "routing_reason" not in result


def test_head_coach_client_omits_null_fields_on_return_to_user(monkeypatch):
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "next_agent": "human",
                "volley_msg_left": 0,
                "routing_reason": None,
                "needs_clarification": False,
                "safety_flags": [],
                "messages": [],
                "selected_agent": None,
            }

    monkeypatch.setattr(
        "agents.head_coach_client.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    update = HeadCoachClient().route({"volley_msg_left": 0, "messages": []})
    assert update["next_agent"] == "human"
    assert "routing_reason" not in update
    assert "selected_agent" not in update
    os.environ.pop("INTERNAL_SERVICE_TOKEN", None)
