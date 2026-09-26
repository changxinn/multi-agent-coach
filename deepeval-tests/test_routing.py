"""Exact routing assertions catch errors without a subjective judge."""

import pytest


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Plan a beginner squat workout.", "training_planner"),
        ("What should I eat for lunch to get more protein?", "nutrition_advisor"),
        ("I slept five hours and feel sore. How should I recover?", "recovery_coach"),
        ("I have a gym program. Please help with my meals.", "nutrition_advisor"),
    ],
)
def test_specialist_routing(route, text, expected):
    result = route(text)
    assert result["next_agent"] == result["selected_agent"] == expected
    assert result["volley_msg_left"] == 1
    assert result["needs_clarification"] is False
    assert result["safety_flags"] == []
    assert (
        result["routing_reason"] == "LLM selected a specialist for the latest message."
    )


def test_latest_message_overrides_old_topic(route):
    result = route(
        "What should I eat for breakfast?",
        history=[{"role": "user", "content": "Plan my squat workout."}],
    )
    assert result["next_agent"] == "nutrition_advisor"


def test_greeting_stays_with_head_coach(route):
    result = route("Hello")
    assert result["next_agent"] == "human"
    assert result["needs_clarification"] is True
    assert result["messages"][0]["content"].strip()
