"""Trusted durable chat summary and Nutrition-context regression coverage."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.chat_context_builder import ChatContextBuilder
from app.services.chat_history_service import ChatHistoryService, ChatSessionView


class _Repository:
    def __init__(self, messages: list[object]) -> None:
        self.messages = messages
        self.calls: list[tuple[int, int]] = []

    async def messages_after(self, _: object, sequence: int, limit: int) -> list[object]:
        self.calls.append((sequence, limit))
        return [message for message in self.messages if message.sequence > sequence][-limit:]


@pytest.mark.asyncio
async def test_context_uses_one_summary_and_only_messages_after_authoritative_boundary() -> None:
    messages = [
        SimpleNamespace(sequence=index, role="user" if index % 2 else "assistant", content=f"m{index}")
        for index in range(1, 27)
    ]
    repository = _Repository(messages)
    view = SimpleNamespace(record=SimpleNamespace(
        history_start_sequence=0, summary_through_sequence=20, summary="trusted summary"
    ))

    context = await ChatContextBuilder(repository).build(view)

    assert context == {
        "version": "chat-history-v1",
        "summary": "trusted summary",
        "messages": [
            {"role": "user" if index % 2 else "assistant", "content": f"m{index}"}
            for index in range(21, 27)
        ],
    }
    assert repository.calls == [(20, 24)]


@pytest.mark.asyncio
async def test_summary_failure_retains_prior_summary_and_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    eligible = [SimpleNamespace(sequence=index, role="user", content=f"m{index}") for index in range(1, 21)]
    repository = _Repository(eligible)
    persisted: list[tuple[str, int]] = []

    async def set_summary(_: object, summary: str, through_sequence: int) -> None:
        persisted.append((summary, through_sequence))

    repository.set_summary = set_summary  # type: ignore[attr-defined]

    class _SummaryService:
        async def summarize(self, *_: object) -> None:
            return None

    monkeypatch.setattr(
        "app.services.chat_history_service.get_settings",
        lambda: SimpleNamespace(CHAT_SUMMARY_TURN_INTERVAL=10),
    )
    service = ChatHistoryService(object(), summary_service=_SummaryService())
    service.repository = repository  # type: ignore[assignment]
    view = ChatSessionView(
        session_id="chat_" + "0" * 32,
        user_id=1,
        profile={},
        messages=[],
        record=SimpleNamespace(history_start_sequence=0, summary_through_sequence=0, summary="prior"),
    )

    await service._roll_summary(view)

    assert persisted == []
    assert view.record.summary == "prior"
    assert view.record.summary_through_sequence == 0