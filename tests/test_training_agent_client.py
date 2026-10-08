from datetime import date

import pytest

from app.config import get_settings
from app.services.training_agent_client import TrainingAgentClient


@pytest.mark.asyncio
async def test_daily_workout_uses_private_authenticated_contract(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    settings = get_settings()
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TRAINING_AGENT_URL", "http://training-agent:8005")
    captured = {}

    class Response:
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
