import logging
from datetime import date
from time import monotonic
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from services.training_agent.app import service as module
from services.training_agent.app.schemas import DailyWorkoutRequest


@pytest.mark.parametrize(
    "error,reason,status",
    [
        (
            APITimeoutError(request=httpx.Request("POST", "https://example.com")),
            "provider_timeout",
            None,
        ),
        (
            APIConnectionError(
                message="PRIVATE-DATA",
                request=httpx.Request("POST", "https://example.com"),
            ),
            "connection_failed",
            None,
        ),
        (
            APIStatusError(
                "PRIVATE-DATA",
                response=httpx.Response(
                    401,
                    request=httpx.Request("POST", "https://example.com"),
                    headers={"x-request-id": "req-123"},
                ),
                body={"secret": "PRIVATE-DATA"},
            ),
            "authentication_failed",
            401,
        ),
        (
            APIStatusError(
                "PRIVATE-DATA",
                response=httpx.Response(
                    429, request=httpx.Request("POST", "https://example.com")
                ),
                body=None,
            ),
            "rate_limited",
            429,
        ),
        (ValueError("PRIVATE-DATA"), "unexpected_error", None),
    ],
)
def test_failure_logs_safe_provider_metadata(
    monkeypatch, caplog, error, reason, status
):
    monkeypatch.setattr(module.settings, "OPENAI_API_KEY", "SECRET-KEY")
    module._log_failure(
        "daily_workout",
        "operation-123",
        monotonic(),
        "llm_response",
        error,
        "deterministic",
    )
    assert f"reason={reason}" in caplog.text
    assert f"provider_status={status}" in caplog.text
    assert "operation_id=operation-123" in caplog.text
    assert "PRIVATE-DATA" not in caplog.text
    assert "SECRET-KEY" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_missing_key_guidance_logs_correlated_fallback(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    monkeypatch.setattr(module.settings, "OPENAI_API_KEY", "")
    assert (
        await module.TrainingService._generate_exercise_guidance("PRIVATE-QUERY")
        == module.SAFE_GUIDANCE_FALLBACK
    )
    assert "stage=configuration" in caplog.text
    assert "reason=missing_api_key" in caplog.text
    assert "generation_source=safe_fallback outcome=returned" in caplog.text
    ids = [
        record.getMessage().split("operation_id=")[1].split()[0]
        for record in caplog.records
    ]
    assert len(ids) == 2 and ids[0] == ids[1]
    assert "PRIVATE-QUERY" not in caplog.text


@pytest.mark.asyncio
async def test_guidance_validation_logs_without_response_content(monkeypatch, caplog):
    monkeypatch.setattr(module.settings, "OPENAI_API_KEY", "SECRET-KEY")
    model = Mock()
    model.invoke.return_value = Mock(content="system prompt PRIVATE-RESPONSE")
    monkeypatch.setattr(module, "ChatOpenAI", Mock(return_value=model))
    assert (
        await module.TrainingService._generate_exercise_guidance("PRIVATE-QUERY")
        == module.SAFE_GUIDANCE_FALLBACK
    )
    assert "stage=guidance_validation" in caplog.text
    assert "reason=invalid_structure" in caplog.text
    for value in ("SECRET-KEY", "PRIVATE-RESPONSE", "PRIVATE-QUERY"):
        assert value not in caplog.text


@pytest.mark.asyncio
async def test_daily_missing_key_logs_fallback_write_and_reuse(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    monkeypatch.setattr(module.settings, "OPENAI_API_KEY", "")
    saved = Mock()
    row = {"created_at": "2026-10-14", "title": "Fallback"}
    saved.mappings.return_value.one.return_value = row
    saved.mappings.return_value.first.return_value = row
    db = Mock()
    db.execute = AsyncMock(return_value=saved)
    service = module.TrainingService(db)
    service.context = AsyncMock(return_value={"private": "PRIVATE-PROFILE"})
    service.profile = AsyncMock(return_value={})
    payload = DailyWorkoutRequest(user_id=1, date=date(2026, 10, 14), refresh=True)
    result = await service.daily_workout(payload)
    assert result["generation_source"] == "deterministic_fallback"
    assert "reason=missing_api_key" in caplog.text
    assert "outcome=database_write_completed" in caplog.text
    assert "PRIVATE-PROFILE" not in caplog.text
    ids = [
        record.getMessage().split("operation_id=")[1].split()[0]
        for record in caplog.records
    ]
    assert len(ids) == 2 and ids[0] == ids[1]
    caplog.clear()
    payload.refresh = False
    assert (await service.daily_workout(payload))["reused"] is True
    assert "generation_source=persisted outcome=reused" in caplog.text
