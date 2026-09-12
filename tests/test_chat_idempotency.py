"""Replay and conflict behavior for idempotent sync and SSE chat turns."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import chat as chat_route
from app.api.schemas.chat import ChatRequest
from app.services.chat_history_service import ChatTurnConflictError

KEY = "6d6e664d-968a-4a39-8efe-344bc24814a4"
SESSION_ID = "chat_0123456789abcdef0123456789abcdef"


class _ProfileService:
    def __init__(self, _: object) -> None:
        pass

    async def get_user_profile(self, _: int) -> dict[str, str]:
        return {"name": "Taylor"}


class _HistoryService:
    mode = "new"
    completed_calls = 0
    failed_calls = 0

    def __init__(self, _: object) -> None:
        pass

    async def build_view(self, *_: object) -> SimpleNamespace:
        return SimpleNamespace(session_id=SESSION_ID, user_id=42, messages=[])

    async def claim_turn(self, *_: object) -> tuple[SimpleNamespace, SimpleNamespace, bool]:
        view = SimpleNamespace(session_id=SESSION_ID, user_id=42, messages=[])
        if self.mode == "completed":
            return view, SimpleNamespace(response_text="saved response", response_metadata={"saved": True}), False
        if self.mode == "processing":
            raise ChatTurnConflictError("A request with this idempotency key is still processing")
        if self.mode == "mismatch":
            raise ChatTurnConflictError("Idempotency key was used with different request content")
        return view, SimpleNamespace(response_text=None, response_metadata=None), True

    async def nutrition_context(self, *_: object) -> dict[str, object]:
        return {"version": "chat-history-v1", "summary": None, "messages": []}

    async def complete_turn(self, *_: object) -> None:
        type(self).completed_calls += 1

    async def fail_turn(self, *_: object) -> None:
        type(self).failed_calls += 1


class _Orchestrator:
    calls = 0
    fails = False

    async def process_message_with_metadata(self, **_: object) -> tuple[str, dict[str, bool]]:
        self.calls += 1
        if self.fails:
            raise RuntimeError("generation failed")
        return "fresh response", {"fresh": True}

    async def process_message_stream(self, **_: object):
        self.calls += 1
        yield {"type": "token", "token": "fresh response"}
        yield {"type": "complete", "metadata": {"fresh": True}}


@pytest.fixture(autouse=True)
def fake_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    _HistoryService.mode = "new"
    _HistoryService.completed_calls = 0
    _HistoryService.failed_calls = 0
    _Orchestrator.calls = 0
    _Orchestrator.fails = False
    monkeypatch.setattr(chat_route, "UserProfileService", _ProfileService)
    monkeypatch.setattr(chat_route, "ChatHistoryService", _HistoryService)
    monkeypatch.setattr(chat_route, "get_orchestrator", lambda: _Orchestrator())


def _request(content: str = "hello") -> ChatRequest:
    return ChatRequest(messages=[{"role": "user", "content": content}], session_id=SESSION_ID)


@pytest.mark.asyncio
async def test_completed_sync_retry_replays_without_orchestration() -> None:
    _HistoryService.mode = "completed"
    response = await chat_route.chat(_request(), KEY, {"id": 42}, object())
    assert response.message == "saved response"
    assert response.metadata == {"saved": True}
    assert _Orchestrator.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["processing", "mismatch"])
async def test_sync_conflicting_idempotency_key_returns_conflict(mode: str) -> None:
    _HistoryService.mode = mode
    with pytest.raises(HTTPException) as error:
        await chat_route.chat(_request(), KEY, {"id": 42}, object())
    assert error.value.status_code == 409
    assert _Orchestrator.calls == 0


@pytest.mark.asyncio
async def test_failed_generation_marks_turn_for_safe_retry() -> None:
    _Orchestrator.fails = True
    with pytest.raises(RuntimeError, match="generation failed"):
        await chat_route.chat(_request(), KEY, {"id": 42}, object())
    assert _HistoryService.failed_calls == 1


@pytest.mark.asyncio
async def test_completed_sse_retry_replays_persisted_response() -> None:
    _HistoryService.mode = "completed"
    response = await chat_route.chat_stream("hello", SESSION_ID, KEY, {"id": 42}, object())
    events = [
        json.loads(line.removeprefix("data: "))
        for line in "".join([chunk async for chunk in response.body_iterator]).splitlines()
        if line.startswith("data: ")
    ]
    assert events == [
        {"token": "saved response", "session_id": SESSION_ID, "is_complete": False},
        {"token": "", "session_id": SESSION_ID, "is_complete": True, "metadata": {"saved": True}},
    ]
    assert _Orchestrator.calls == 0