"""SSE chat route regression coverage."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.api.routes import chat as chat_route


class _ProfileService:
    def __init__(self, _: object) -> None:
        pass

    async def get_user_profile(self, _: int) -> dict[str, str]:
        return {"name": "Taylor"}


class _HistoryService:
    def __init__(self, _: object) -> None:
        pass

    async def build_view(self, *_: object) -> SimpleNamespace:
        return SimpleNamespace(session_id="chat_0123456789abcdef", messages=[])

    async def append_user_message(self, *_: object) -> None:
        pass

    async def append_assistant_message(self, *_: object) -> None:
        pass

    async def nutrition_context(self, *_: object) -> dict[str, object]:
        return {"version": "chat-history-v1", "summary": None, "messages": []}


class _Orchestrator:
    async def process_message_stream(self, **kwargs: object):
        assert kwargs["chat_context"] == {"version": "chat-history-v1", "summary": None, "messages": []}
        yield {"type": "token", "token": "Profile "}
        yield {"type": "token", "token": "setup is required."}
        yield {
            "type": "complete",
            "metadata": {
                "nutrition_status": "profile_required",
                "nutrition_profile_required": True,
            },
        }


@pytest.mark.asyncio
async def test_chat_stream_includes_metadata_in_completion_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chat_route, "UserProfileService", _ProfileService)
    monkeypatch.setattr(chat_route, "ChatHistoryService", _HistoryService)
    monkeypatch.setattr(chat_route, "get_orchestrator", lambda: _Orchestrator())

    response = await chat_route.chat_stream(
        message="Give me a nutrition plan",
        session_id="chat_0123456789abcdef",
        current_user={"id": 42},
        db=object(),
    )
    payload = "".join([chunk async for chunk in response.body_iterator])
    events = [json.loads(line.removeprefix("data: ")) for line in payload.splitlines() if line.startswith("data: ")]

    assert "".join(event["token"] for event in events[:-1]) == "Profile setup is required."
    assert all(event["is_complete"] is False for event in events[:-1])
    assert events[-1] == {
        "token": "",
        "session_id": "chat_0123456789abcdef",
        "is_complete": True,
        "metadata": {
            "nutrition_status": "profile_required",
            "nutrition_profile_required": True,
        },
    }
    assert response.headers["x-accel-buffering"] == "no"