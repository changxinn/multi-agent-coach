from unittest.mock import AsyncMock, Mock

import pytest

from services.training_agent.app import service as module
from services.training_agent.app.service import SAFE_GUIDANCE_FALLBACK, TrainingService


@pytest.mark.asyncio
async def test_catalogued_exercise_guidance_does_not_call_llm(monkeypatch):
    db = Mock()
    result = Mock()
    result.mappings.return_value = [{"name": "squat", "guidance": "Brace."}]
    db.execute = AsyncMock(return_value=result)
    service = TrainingService(db)
    generate = AsyncMock()
    monkeypatch.setattr(service, "_generate_exercise_guidance", generate)

    items = await service.exercise_guidance("squat")

    assert items == [{"name": "squat", "guidance": "Brace."}]
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_exercise_generates_guidance(monkeypatch):
    service = TrainingService(Mock())
    monkeypatch.setattr(service, "exercises", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service,
        "_generate_exercise_guidance",
        AsyncMock(return_value="Keep your elbows soft."),
    )

    items = await service.exercise_guidance("chest flys")

    assert items == [{"name": "chest flys", "guidance": "Keep your elbows soft."}]


@pytest.mark.asyncio
async def test_unknown_exercise_uses_safe_fallback_without_llm_key(monkeypatch):
    monkeypatch.setattr(module.settings, "OPENAI_API_KEY", "")

    assert (
        await TrainingService._generate_exercise_guidance("chest flys")
        == SAFE_GUIDANCE_FALLBACK
    )
