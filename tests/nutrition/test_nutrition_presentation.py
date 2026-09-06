"""Nutrition presentation keeps deterministic safety language intact."""

from datetime import UTC, datetime
from types import SimpleNamespace

from services.nutrition_agent.app import agent as nutrition_agent_module
from services.nutrition_agent.app.agent import NutritionAgent
from services.nutrition_agent.app.assessment import DISCLAIMER, REFERRAL
from services.nutrition_agent.app.schemas import Escalation, NutritionEvaluateResponse


def assessment(*, escalation: Escalation | None = None) -> NutritionEvaluateResponse:
    return NutritionEvaluateResponse(
        status="escalate" if escalation else "green",
        score=10 if escalation else 0,
        message="Deterministic assessment.",
        recommendations=["Seek qualified healthcare support."] if escalation else ["Continue consistent habits."],
        escalation=escalation,
        created_at=datetime.now(UTC),
    )


def test_disabled_presentation_preserves_one_disclaimer() -> None:
    result = NutritionAgent(type("Settings", (), {"NUTRITION_LLM_ENABLED": False})()).present(
        assessment(), "untrusted content"
    )

    assert result.message.count(DISCLAIMER) == 1
    assert "untrusted content" not in result.message


def test_escalation_presentation_preserves_referral_and_disclaimer() -> None:
    escalation = Escalation(message=REFERRAL, urgent=True)
    result = NutritionAgent(type("Settings", (), {"NUTRITION_LLM_ENABLED": False})()).present(
        assessment(escalation=escalation), "untrusted content"
    )

    assert REFERRAL in result.message
    assert result.message.count(DISCLAIMER) == 1


def test_llm_presentation_uses_gpt5_completion_token_parameter(monkeypatch) -> None:
    request: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(
            self,
            *,
            model: str,
            reasoning_effort: str,
            max_completion_tokens: int,
            messages: list[dict[str, str]],
        ) -> object:
            request.update(
                model=model,
                reasoning_effort=reasoning_effort,
                max_completion_tokens=max_completion_tokens,
                messages=messages,
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Keep building consistent habits."))]
            )

    monkeypatch.setattr(nutrition_agent_module, "OpenAI", FakeOpenAI)
    settings = type("Settings", (), {
        "NUTRITION_LLM_ENABLED": True,
        "OPENAI_API_KEY": "test-key",
        "LLM_MODEL": "gpt-5-nano",
    })()

    result = NutritionAgent(settings).present(assessment(), "untrusted content")

    assert request["reasoning_effort"] == "minimal"
    assert request["max_completion_tokens"] == 500
    assert "max_tokens" not in request
    assert "temperature" not in request
    assert "Keep building consistent habits." in result.message
    assert result.message.count(DISCLAIMER) == 1


def test_llm_presentation_empty_content_uses_safe_fallback(monkeypatch, caplog) -> None:
    class FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(
            self,
            *,
            model: str,
            reasoning_effort: str,
            max_completion_tokens: int,
            messages: list[dict[str, str]],
        ) -> object:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="length",
                        message=SimpleNamespace(content=None, refusal=None),
                    )
                ]
            )

    monkeypatch.setattr(nutrition_agent_module, "OpenAI", FakeOpenAI)
    settings = type("Settings", (), {
        "NUTRITION_LLM_ENABLED": True,
        "OPENAI_API_KEY": "test-key",
        "LLM_MODEL": "gpt-5-nano",
    })()

    result = NutritionAgent(settings).present(assessment(), "untrusted content")

    assert result.message == "Deterministic assessment.\n\n*" + DISCLAIMER + "*"
    assert "content_empty=True" in caplog.text
    assert "finish_reason=length" in caplog.text