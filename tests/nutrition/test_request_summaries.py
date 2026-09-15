"""Deterministic Nutrition request-summary coverage."""

from __future__ import annotations

from services.nutrition_agent.app.agent import NutritionAgent
from services.nutrition_agent.app.assessment import NutritionHistory, assess_nutrition
from services.nutrition_agent.app.schemas import NutritionEvaluateRequest


def _assessment(message: str, **kwargs: object):
    return assess_nutrition(NutritionEvaluateRequest(message=message, **kwargs), NutritionHistory(), {
        "dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": [],
    })


def test_summary_describes_constrained_meal_request() -> None:
    assessment = _assessment("Give me a high-protein breakfast under 500 calories.")

    assert assessment.request_summary == (
        "a breakfast meal recommendation with under 500 calories, at least 30 g protein"
    )


def test_summary_describes_validated_weight_loss_meal_revision() -> None:
    assessment = _assessment(
        "Tailor both for weight loss.",
        nutrition_follow_up={
            "nutrition_follow_up": "revise_recent_meal",
            "activity_type": "unspecified",
            "meal_adjustment": "lower_energy",
        },
        chat_context={
            "version": "chat-history-v1",
            "summary": None,
            "messages": [
                {"role": "user", "content": "Give me a breakfast and lunch option."},
                {"role": "assistant", "content": "Here are options."},
                {"role": "user", "content": "Tailor both for weight loss."},
            ],
        },
    )

    assert assessment.request_summary == "revising a recent meal for a lower-energy option"


def test_summary_categorizes_macro_adherence_hydration_and_fueling() -> None:
    assert _assessment("How are my macros and meal logging consistency?").request_summary == (
        "calorie or macronutrient guidance"
    )
    assert _assessment("How much water should I drink for hydration?").request_summary == "hydration guidance"
    assert _assessment("How should I fuel my workout?").request_summary == "nutrition to fuel training"


def test_summary_describes_meal_recall_and_omits_terminal_escalation() -> None:
    recalled = _assessment(
        "What was my previous meal recommendation?",
        nutrition_follow_up={
            "nutrition_follow_up": "recall_recent_meal",
            "activity_type": "unspecified",
            "meal_adjustment": "none",
        },
    )
    escalated = _assessment("I need a meal plan while taking insulin.")

    assert recalled.request_summary == "recalling your most recent meal recommendation"
    assert escalated.status == "escalate"
    assert escalated.request_summary is None


def test_presentation_prepends_summary_for_disabled_and_enabled_paths(monkeypatch) -> None:
    assessment = _assessment("How much water should I drink for hydration?")
    disabled = NutritionAgent(type("Settings", (), {"NUTRITION_LLM_ENABLED": False})()).present(
        assessment, "untrusted"
    )

    assert disabled.message.startswith("**You asked about:** hydration guidance\n\n")

    class FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.chat = type("Chat", (), {"completions": type("Completions", (), {
                "create": lambda *_args, **_kwargs: type("Result", (), {
                    "choices": [type("Choice", (), {
                        "message": type("Message", (), {"content": "Keep it practical."})(),
                    })()],
                })(),
            })()})()

    monkeypatch.setattr("services.nutrition_agent.app.agent.OpenAI", FakeOpenAI)
    enabled = NutritionAgent(type("Settings", (), {
        "NUTRITION_LLM_ENABLED": True, "OPENAI_API_KEY": "test-key", "LLM_MODEL": "test-model",
    })()).present(assessment, "untrusted")

    assert enabled.message.startswith("**You asked about:** hydration guidance\n\nKeep it practical.")


def test_disabled_stream_prepends_summary() -> None:
    assessment = _assessment("How should I fuel my workout?")
    agent = NutritionAgent(type("Settings", (), {
        "NUTRITION_LLM_ENABLED": False, "OPENAI_API_KEY": None,
    })())

    assert "".join(agent.present_stream(assessment, "untrusted")).startswith(
        "**You asked about:** nutrition to fuel training\n\n"
    )


def test_enabled_stream_prepends_trusted_summary_after_provider_initializes(monkeypatch) -> None:
    assessment = _assessment("How much water should I drink for hydration?")

    class FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.chat = type("Chat", (), {"completions": type("Completions", (), {
                "create": lambda *_args, **_kwargs: iter([
                    type("Chunk", (), {"choices": [type("Choice", (), {
                        "delta": type("Delta", (), {"content": "Keep hydration practical."})(),
                    })()]})(),
                ]),
            })()})()

    monkeypatch.setattr("services.nutrition_agent.app.agent.OpenAI", FakeOpenAI)
    agent = NutritionAgent(type("Settings", (), {
        "NUTRITION_LLM_ENABLED": True, "OPENAI_API_KEY": "test-key", "LLM_MODEL": "test-model",
    })())

    assert "".join(agent.present_stream(assessment, "untrusted")).startswith(
        "**You asked about:** hydration guidance\n\nKeep hydration practical."
    )