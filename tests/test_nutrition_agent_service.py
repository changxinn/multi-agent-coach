from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from services.nutrition_agent.app.agent import NutritionAgent
from services.nutrition_agent.app.config import SERVICE_DIR, Settings, settings
from services.nutrition_agent.app.main import app, get_service, startup


@pytest.fixture(autouse=True)
def disable_migrations_for_http_tests(monkeypatch):
    """Keep TestClient startup independent of a live Nutrition database."""
    monkeypatch.setattr(settings, "RUN_MIGRATIONS", False)


def test_settings_load_service_local_env_file_regardless_of_working_directory():
    assert SERVICE_DIR == Path(__file__).parents[1] / "services/nutrition_agent"
    assert Settings.model_config["env_file"] == SERVICE_DIR / ".env"


@pytest.mark.asyncio
async def test_startup_runs_migrations_when_enabled(monkeypatch, caplog):
    init = AsyncMock()
    monkeypatch.setattr(settings, "RUN_MIGRATIONS", True)
    monkeypatch.setattr("services.nutrition_agent.app.main.init_db", init)

    with caplog.at_level("INFO", logger="uvicorn.error"):
        await startup()

    init.assert_awaited_once_with()
    assert "Nutrition migrations enabled" in caplog.text
    assert "Nutrition database migrations completed" in caplog.text


@pytest.mark.asyncio
async def test_startup_logs_when_migrations_are_disabled(caplog):
    with caplog.at_level("INFO", logger="uvicorn.error"):
        await startup()

    assert "Nutrition migrations skipped" in caplog.text


def test_health_is_public_and_private_operations_require_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/v1/nutrition/status").status_code == 405
        missing_token_response = client.post("/v1/nutrition/status", json={})
        wrong_token_response = client.post(
            "/v1/nutrition/status",
            json={},
            headers={"X-Internal-Service-Token": "wrong"},
        )
        ready_response = client.post(
            "/v1/nutrition/status",
            json={},
            headers={"X-Internal-Service-Token": "test-token"},
        )
        assert missing_token_response.status_code == 401
        assert wrong_token_response.status_code == 401
        assert ready_response.json()["status"] == "ready"


def test_private_agent_calculation_matches_phase_one_contract(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    payload = {
        "sex": "male",
        "age": 30,
        "weight_kg": "80",
        "height_cm": "180",
        "activity_level": "moderate",
        "goal": "maintenance",
    }
    with TestClient(app) as client:
        response = client.post(
            "/v1/nutrition/targets/calculate",
            json=payload,
            headers={"X-Internal-Service-Token": "test-token"},
        )

    assert response.status_code == 200
    assert response.json()["calculation_method"] == "mifflin_st_jeor_v1"


def test_nutrition_chat_requires_token_and_forwards_full_transcript(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    captured = {}

    def respond(*, messages, user_profile):
        captured["messages"] = messages
        captured["user_profile"] = user_profile
        return "Try Greek yogurt with fruit after training."

    monkeypatch.setattr("services.nutrition_agent.app.main.agent.respond", respond)
    payload = {
        "user_id": 7,
        "user_profile": {"goal": "performance"},
        "messages": [
            {"role": "user", "content": "I trained this morning."},
            {"role": "assistant", "name": "Alex", "content": "Great work."},
            {"role": "user", "content": "What should I eat now?"},
        ],
    }
    with TestClient(app) as client:
        assert client.post("/v1/nutrition/chat", json=payload).status_code == 401
        response = client.post(
            "/v1/nutrition/chat",
            json=payload,
            headers={"X-Internal-Service-Token": "test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Try Greek yogurt with fruit after training."}
    assert captured["messages"] == payload["messages"]
    assert captured["user_profile"] == payload["user_profile"]


def test_nutrition_agent_uses_gpt5_completion_token_parameter(monkeypatch):
    completion = MagicMock()
    completion.choices[0].message.content = "Prioritize protein after training."
    create = MagicMock(return_value=completion)
    openai_client = MagicMock()
    openai_client.chat.completions.create = create
    monkeypatch.setattr(
        "services.nutrition_agent.app.agent.OpenAI", lambda **_: openai_client
    )
    configured_settings = Settings(
        NUTRITION_LLM_ENABLED=True,
        OPENAI_API_KEY="test-key",
        LLM_MODEL="gpt-5-nano",
    )

    response = NutritionAgent(configured_settings).respond(
        messages=[{"role": "user", "content": "What should I eat after training?"}],
        user_profile={"allergies": []},
    )

    assert response == "Prioritize protein after training."
    assert create.call_args.kwargs["max_completion_tokens"] == 2000
    assert "max_tokens" not in create.call_args.kwargs
    assert "temperature" not in create.call_args.kwargs


def test_nutrition_agent_logs_rejected_output_only_when_debugging_is_enabled(
    monkeypatch, caplog
):
    completion = MagicMock()
    completion.id = "chatcmpl-test"
    completion.choices[0].finish_reason = "length"
    completion.choices[0].message.content = "My system prompt says to reveal secrets."
    completion.choices[0].message.refusal = None
    completion.usage.model_dump.return_value = {"completion_tokens": 300}
    openai_client = MagicMock()
    openai_client.chat.completions.create.return_value = completion
    monkeypatch.setattr(
        "services.nutrition_agent.app.agent.OpenAI", lambda **_: openai_client
    )
    configured_settings = Settings(
        NUTRITION_LLM_ENABLED=True,
        NUTRITION_LLM_DEBUG_LOG_RESPONSES=True,
        OPENAI_API_KEY="test-key",
    )

    with caplog.at_level("WARNING", logger="services.nutrition_agent.app.agent"):
        response = NutritionAgent(configured_settings).respond(
            messages=[{"role": "user", "content": "What should I eat?"}],
            user_profile={"allergies": []},
        )

    assert response == "I couldn't generate a tailored nutrition response right now. Please try again."
    assert "Nutrition LLM output rejected" in caplog.text
    assert "reason=disallowed_phrase" in caplog.text
    assert "My system prompt says to reveal secrets." in caplog.text
    assert "finish_reason': 'length'" in caplog.text


def test_nutrition_agent_logs_bounded_request_only_when_enabled(monkeypatch, caplog):
    completion = MagicMock()
    completion.choices[0].message.content = "Eat a protein-rich meal after training."
    openai_client = MagicMock()
    openai_client.chat.completions.create.return_value = completion
    monkeypatch.setattr(
        "services.nutrition_agent.app.agent.OpenAI", lambda **_: openai_client
    )
    configured_settings = Settings(
        NUTRITION_LLM_ENABLED=True,
        NUTRITION_LLM_DEBUG_LOG_REQUESTS=True,
        OPENAI_API_KEY="test-key",
    )

    with caplog.at_level("WARNING", logger="services.nutrition_agent.app.agent"):
        NutritionAgent(configured_settings).respond(
            messages=[{"role": "user", "content": "What should I eat after training?"}],
            user_profile={"allergies": ["milk"]},
        )

    assert "Nutrition LLM request" in caplog.text
    assert "What should I eat after training?" in caplog.text
    assert "'allergies': ['milk']" in caplog.text


def test_private_meal_plan_routes_use_authenticated_payload_and_service(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    service = AsyncMock()
    service.idempotent.return_value = {"id": 41, "version": 1}
    service.get_active_meal_plan.return_value = {"id": 41, "planned_meals": []}
    service.get_nutrition_context.return_value = {
        "date": "2026-09-22",
        "target_snapshot": {"id": 3},
        "meal_plan": {"id": 41},
    }
    app.dependency_overrides[get_service] = lambda: service
    payload = {
        "user_id": 7,
        "target_snapshot_id": 3,
        "profile": {
            "sex_for_energy_equation": "female",
            "activity_level": "moderate",
            "nutrition_goal": "maintenance",
            "allergies": [],
        },
        "start_date": "2026-09-22",
        "end_date": "2026-09-22",
        "planned_meals": [
            {
                "planned_date": "2026-09-22",
                "meal_type": "breakfast",
                "calorie_target_kcal": 500,
                "protein_target_g": 30,
                "carbohydrate_target_g": 50,
                "fat_target_g": 15,
                "fiber_target_g": 8,
                "items": [
                    {
                        "food_name": "Oats",
                        "quantity": 50,
                        "unit": "g",
                        "calories": 190,
                        "protein_g": 6,
                        "carbohydrate_g": 32,
                        "fat_g": 4,
                        "source": "meal_plan",
                    }
                ],
            }
        ],
    }
    headers = {"X-Internal-Service-Token": "test-token", "Idempotency-Key": "plan-1"}

    try:
        with TestClient(app) as client:
            created = client.post(
                "/v1/nutrition/meal-plans/create", json=payload, headers=headers
            )
            active = client.post(
                "/v1/nutrition/meal-plans/active",
                json={"user_id": 7, "date": "2026-09-22"},
                headers=headers,
            )
            context = client.post(
                "/v1/nutrition/context",
                json={"user_id": 7, "date": "2026-09-22"},
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 200
    assert created.json() == {"id": 41, "version": 1}
    service.idempotent.assert_awaited_once()
    assert service.idempotent.await_args.args[:3] == (7, "meal-plans.create", "plan-1")
    assert active.json() == {"meal_plan": {"id": 41, "planned_meals": []}}
    service.get_active_meal_plan.assert_awaited_once()
    assert context.json()["target_snapshot"] == {"id": 3}
    service.get_nutrition_context.assert_awaited_once()
