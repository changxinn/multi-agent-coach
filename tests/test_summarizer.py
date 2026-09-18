import pytest

from agents.summarizer import build_structured_summary, summarizer


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("USE_SUMMARIZER_SERVICE", raising=False)


def test_structured_summary_includes_profile_and_progress():
    summary = build_structured_summary(
        {
            "user_profile": {"goal": "Hyrox", "fitness_level": "beginner"},
            "messages": [
                {"role": "user", "content": "You: Plan a workout"},
                {
                    "role": "assistant",
                    "name": "Alex (Training Planner)",
                    "content": "Alex (Training Planner): Do goblet squats.",
                },
            ],
            "safety_flags": [],
        },
        progress="Workouts logged: 1",
    )
    assert "Hyrox" in summary
    assert "training" in summary.lower()
    assert "Workouts logged: 1" in summary
    assert "Alex" in summary or "training_planner" in summary


def test_summarizer_falls_back_without_llm(monkeypatch):
    monkeypatch.setenv("SUMMARIZER_SERVICE_MODE", "true")
    monkeypatch.delenv("USE_SUMMARIZER_SERVICE", raising=False)
    text = summarizer(
        {
            "messages": [{"role": "user", "content": "You: I slept 8 hours"}],
            "user_profile": {"goal": "strength", "fitness_level": "intermediate"},
        }
    )
    assert "SESSION SUMMARY" in text
    assert "strength" in text
