"""Nutrition presentation keeps deterministic safety language intact."""

from datetime import UTC, datetime
from types import SimpleNamespace

from services.nutrition_agent.app import agent as nutrition_agent_module
from services.nutrition_agent.app.agent import NutritionAgent
from services.nutrition_agent.app.assessment import DISCLAIMER, REFERRAL
from services.nutrition_agent.app.schemas import Escalation, MealRecommendation, NutritionEvaluateResponse


def assessment(*, escalation: Escalation | None = None) -> NutritionEvaluateResponse:
    return NutritionEvaluateResponse(
        status="escalate" if escalation else "green",
        score=10 if escalation else 0,
        message="Deterministic assessment.",
        recommendations=["Seek qualified healthcare support."] if escalation else ["Continue consistent habits."],
        escalation=escalation,
        created_at=datetime.now(UTC),
    )


def meal_assessment() -> NutritionEvaluateResponse:
    return NutritionEvaluateResponse(
        status="green",
        score=1,
        message="- **Lean beef with sweet potato**: about 520 calories and 42 g protein.",
        recommendations=["**Lean beef with sweet potato**: about 520 calories and 42 g protein."],
        meal_recommendations=[MealRecommendation(meal_type="dinner", name="Lean beef with sweet potato", calories=520, protein_g=42, carbs_g=45, fiber_g=7, fat_g=22, satisfies=["protein"])],
        created_at=datetime.now(UTC),
    )


def balanced_meal_assessment() -> NutritionEvaluateResponse:
    return NutritionEvaluateResponse(
        status="green",
        score=1,
        message=(
            "- **Salmon with brown rice and broccoli**: about 550 calories, 40 g protein, "
            "45 g carbohydrates, and 8 g fiber."
        ),
        recommendations=[
            "**Salmon with brown rice and broccoli**: about 550 calories, 40 g protein, "
            "45 g carbohydrates, and 8 g fiber."
        ],
        meal_recommendations=[MealRecommendation(meal_type="dinner", name="Salmon with brown rice and broccoli", calories=550, protein_g=40, carbs_g=45, fiber_g=8, fat_g=22, satisfies=["protein", "carbohydrates", "fiber", "fat"])],
        created_at=datetime.now(UTC),
    )


def _llm_settings() -> object:
    return type("Settings", (), {
        "NUTRITION_LLM_ENABLED": True,
        "OPENAI_API_KEY": "test-key",
        "LLM_MODEL": "gpt-5-nano",
    })()


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


def test_llm_presentation_uses_deterministic_meal_when_model_omits_it(monkeypatch, caplog) -> None:
    class FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs: object) -> object:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content="Review your daily targets and check meal feasibility."
                ))]
            )

    monkeypatch.setattr(nutrition_agent_module, "OpenAI", FakeOpenAI)

    result = NutritionAgent(_llm_settings()).present(meal_assessment(), "Give me a high-protein dinner.")

    assert "Lean beef with sweet potato" in result.message
    assert "520 calories" in result.message
    assert "42 g protein" in result.message
    assert "Review your daily targets and check meal feasibility." in result.message
    assert "missing_meal_facts" not in caplog.text


def test_llm_presentation_accepts_output_that_preserves_deterministic_meal(monkeypatch) -> None:
    class FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs: object) -> object:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content="- Lean beef with sweet potato: 520 calories and 42 g protein."
                ))]
            )

    monkeypatch.setattr(nutrition_agent_module, "OpenAI", FakeOpenAI)

    result = NutritionAgent(_llm_settings()).present(meal_assessment(), "Give me a high-protein dinner.")

    assert result.message.startswith("- **Lean beef with sweet potato**: about 520 calories and 42 g protein.")
    assert "- Lean beef with sweet potato: 520 calories and 42 g protein." in result.message


def test_llm_presentation_uses_deterministic_balanced_meal_when_model_omits_fiber(monkeypatch, caplog) -> None:
    class FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs: object) -> object:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content="- Salmon with brown rice and broccoli: 550 calories, 40 g protein, and 45 g carbohydrates."
                ))]
            )

    monkeypatch.setattr(nutrition_agent_module, "OpenAI", FakeOpenAI)

    result = NutritionAgent(_llm_settings()).present(
        balanced_meal_assessment(), "Give me a balanced dinner with carbs, protein, and fiber."
    )

    assert "8 g fiber" in result.message
    assert "missing_meal_facts" not in caplog.text


def test_llm_presentation_accepts_output_that_preserves_balanced_meal_facts(monkeypatch) -> None:
    class FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs: object) -> object:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content="- Salmon with brown rice and broccoli: 550 calories, 40 g protein, 45 g carbs, and 8 g fiber."
                ))]
            )

    monkeypatch.setattr(nutrition_agent_module, "OpenAI", FakeOpenAI)

    result = NutritionAgent(_llm_settings()).present(
        balanced_meal_assessment(), "Give me a balanced dinner with carbs, protein, and fiber."
    )

    assert result.message.startswith(
        "- **Salmon with brown rice and broccoli**: about 550 calories, 40 g protein, "
        "45 g carbohydrates, and 8 g fiber."
    )
    assert "- Salmon with brown rice and broccoli: 550 calories, 40 g protein, 45 g carbs, and 8 g fiber." in result.message