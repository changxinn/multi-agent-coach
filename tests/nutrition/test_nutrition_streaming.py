"""Private Nutrition SSE evaluation and client parsing coverage."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.services.nutrition_agent_client import NutritionAgentClient
from services.nutrition_agent.app import main as nutrition_main
from services.nutrition_agent.app.assessment import NutritionHistory
from services.nutrition_agent.app.schemas import NutritionEvaluateRequest, NutritionEvaluateResponse


def _assessment() -> NutritionEvaluateResponse:
    return NutritionEvaluateResponse(
        status="green", score=0, message="Deterministic assessment.",
        recommendations=["Continue consistent habits."], created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_private_stream_emits_tokens_then_persisted_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[NutritionEvaluateResponse] = []

    async def history(_: int) -> NutritionHistory:
        return NutritionHistory()

    async def save(_: int, assessment: NutritionEvaluateResponse) -> None:
        saved.append(assessment)

    monkeypatch.setattr(nutrition_main.repository, "history", history)
    monkeypatch.setattr(nutrition_main.repository, "save_assessment", save)
    monkeypatch.setattr(nutrition_main.agent, "present_stream", lambda *_: iter(["Hello", " world."]))

    response = await nutrition_main.evaluate_stream(42, NutritionEvaluateRequest(message="Help me eat well."))
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "event: token\ndata: {\"token\": \"Hello world.\"}" in body
    assert "event: complete" in body
    assert len(saved) == 1
    assert saved[0].message.startswith("Hello world.")
    assert response.headers["x-accel-buffering"] == "no"


@pytest.mark.asyncio
async def test_private_stream_uses_deterministic_fallback_before_visible_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def history(_: int) -> NutritionHistory:
        return NutritionHistory()

    async def save(_: int, __: NutritionEvaluateResponse) -> None:
        return None

    def broken_stream(*_: object):
        raise RuntimeError("provider unavailable")
        yield "unreachable"

    monkeypatch.setattr(nutrition_main.repository, "history", history)
    monkeypatch.setattr(nutrition_main.repository, "save_assessment", save)
    monkeypatch.setattr(nutrition_main.agent, "present_stream", broken_stream)

    response = await nutrition_main.evaluate_stream(42, NutritionEvaluateRequest(message="Help me eat well."))
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "event: error" not in body
    assert "All nutrition advice is for general informational purposes only" in body
    assert "event: complete" in body


@pytest.mark.asyncio
async def test_client_parses_token_and_complete_events(monkeypatch: pytest.MonkeyPatch) -> None:
    client = NutritionAgentClient()
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.get_settings",
        lambda: type("Settings", (), {"NUTRITION_INTERNAL_SERVICE_TOKEN": "token", "NUTRITION_AGENT_URL": "http://nutrition"})(),
    )
    completion = _assessment().model_dump(mode="json")
    stream = (
        'event: token\ndata: {"token":"Hello "}\n\n'
        f"event: complete\ndata: {json.dumps(completion)}\n\n"
    ).encode()

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=stream, headers={"content-type": "text/event-stream"})

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    events = [event async for event in client.evaluate_stream(42, "Hello")]
    await client.close()

    assert events == [
        {"type": "token", "token": "Hello "},
        {"type": "complete", "assessment": completion},
    ]