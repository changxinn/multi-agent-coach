"""Safety coverage for local LangChain specialist streaming."""

from __future__ import annotations

import importlib

import pytest
from langchain_core.messages import AIMessageChunk

specialist_module = importlib.import_module("agents.specialist")


class _StreamingLlm:
    async def astream(self, _: object):
        for text in ("Thought: private reasoning\n", "Message: Hello", " athlete!"):
            yield AIMessageChunk(content=text)


@pytest.mark.asyncio
async def test_specialist_stream_emits_only_public_message_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(specialist_module, "ChatOpenAI", lambda **_: _StreamingLlm())
    emitted: list[str] = []

    result = await specialist_module.specialist_stream(
        "training_planner",
        {
            "messages": [{"role": "user", "content": "You: Help me train."}],
            "user_profile": {},
        },
        emitted.append,
    )

    assert "".join(emitted) == "Hello athlete!"
    assert "Thought:" not in "".join(emitted)
    assert result["messages"][0]["content"] == "Alex (Training Planner): Hello athlete!"