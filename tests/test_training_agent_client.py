from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.config import get_settings
from app.services.training_agent_client import (
    TrainingAgentClient,
    TrainingAgentUnavailableError,
)


@pytest.mark.asyncio
async def test_daily_workout_uses_private_authenticated_contract(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    settings = get_settings()
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TRAINING_AGENT_URL", "http://training-agent:8005")
    captured = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "ready"}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return Response()

    monkeypatch.setattr(
        "app.services.training_agent_client.httpx.AsyncClient", lambda **_: Client()
    )
    result = await TrainingAgentClient().daily_workout(
        user_id=7,
        workout_date=date(2026, 10, 7),
        refresh=False,
        recovery_status="green",
    )

    assert result == {"status": "ready"}
    assert captured["url"] == "http://training-agent:8005/v1/training/daily-workout"
    assert captured["headers"]["X-Internal-Service-Token"] == "test-token"
    assert captured["json"]["user_id"] == 7


@pytest.mark.asyncio
async def test_client_maps_configuration_and_http_failures(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "")
    client = TrainingAgentClient()
    with pytest.raises(TrainingAgentUnavailableError, match="not configured"):
        await client.progress(1, 7)
    with pytest.raises(TrainingAgentUnavailableError, match="not configured"):
        client.respond(1, [], {})

    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "token")

    class FailedClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, *_args, **_kwargs):
            import httpx

            raise httpx.ConnectError("down")

    monkeypatch.setattr(
        "app.services.training_agent_client.httpx.AsyncClient",
        lambda **_: FailedClient(),
    )
    with pytest.raises(TrainingAgentUnavailableError, match="temporarily unavailable"):
        await client.progress(1, 7)


@pytest.mark.asyncio
async def test_client_wrappers_forward_payloads_and_limit_lists(monkeypatch):
    client = TrainingAgentClient()
    post = AsyncMock(return_value={"items": [1, 2, 3]})
    monkeypatch.setattr(client, "_post", post)

    assert await client.exercises_search(1, "squat") == {"items": [1, 2, 3]}
    assert await client.exercise_lookup(1, "squat") == {"items": [1, 2, 3]}
    assert await client.generate_program(1, "green") == {"items": [1, 2, 3]}
    assert await client.list_programs(1) == {"items": [1, 2, 3]}
    assert await client.adapt_program(1, "fatigue", "amber") == {"items": [1, 2, 3]}
    assert await client.profile(1) == {"items": [1, 2, 3]}
    assert await client.update_profile(1, {"fitness_goal": "strength"}) == {
        "items": [1, 2, 3]
    }
    assert await client.preferences(1) == {"items": [1, 2, 3]}
    assert await client.update_preferences(1, {"equipment": ["barbell"]}) == {
        "items": [1, 2, 3]
    }
    assert await client.log_workout(1, {"description": "lift"}, "key") == {
        "items": [1, 2, 3]
    }
    assert await client.list_workouts(1, 28, 2) == {"items": [1, 2]}
    assert await client.progress(1, 28) == {"items": [1, 2, 3]}
    assert await client.context(1) == {"items": [1, 2, 3]}
    assert any(
        call.kwargs.get("idempotency_key") == "key" for call in post.await_args_list
    )


def test_respond_maps_http_failures(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "token")
    import httpx

    monkeypatch.setattr(
        "app.services.training_agent_client.httpx.post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ConnectError("down")),
    )
    client = TrainingAgentClient()
    with pytest.raises(TrainingAgentUnavailableError, match="temporarily unavailable"):
        client.respond(1, [], {})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation,expected_timeout",
    [
        ("programs/generate", 90),
        ("programs/adapt", 90),
        ("daily-workout", 90),
        ("exercises/search", 90),
        ("exercises/lookup", 20),
        ("programs/list", 20),
        ("context", 20),
        ("preferences/get", 20),
    ],
)
async def test_operation_timeout_budgets(monkeypatch, operation, expected_timeout):
    import httpx

    settings = get_settings()
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "token")
    monkeypatch.setattr(settings, "TRAINING_AGENT_TIMEOUT_SECONDS", 20)
    monkeypatch.setattr(settings, "TRAINING_AGENT_GENERATION_TIMEOUT_SECONDS", 90)
    captured = {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, **kwargs):
            return httpx.Response(
                200, json={"ok": True}, request=httpx.Request("POST", url)
            )

    def make_client(**kwargs):
        captured.update(kwargs)
        return Client()

    monkeypatch.setattr(
        "app.services.training_agent_client.httpx.AsyncClient", make_client
    )
    assert await TrainingAgentClient()._post(operation, {"user_id": 1}) == {"ok": True}
    assert captured["timeout"].read == expected_timeout
    assert captured["timeout"].connect == 2


@pytest.mark.asyncio
async def test_generation_timeout_is_logged_and_not_retried(monkeypatch, caplog):
    import httpx

    monkeypatch.setattr(get_settings(), "INTERNAL_SERVICE_TOKEN", "token")
    post = AsyncMock(
        side_effect=httpx.ReadTimeout("private payload must not be logged")
    )

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    client = Client()
    client.post = post
    monkeypatch.setattr(
        "app.services.training_agent_client.httpx.AsyncClient", lambda **_: client
    )
    with pytest.raises(TrainingAgentUnavailableError, match="check saved programs"):
        await TrainingAgentClient().generate_program(1, "green")
    post.assert_awaited_once()
    assert "operation=programs/generate error_type=ReadTimeout" in caplog.text
    assert "elapsed_seconds=" in caplog.text
    assert "private payload" not in caplog.text
