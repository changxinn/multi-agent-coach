"""Regression coverage for asynchronous LangGraph orchestration."""

from __future__ import annotations

import pytest

from app.services import agent_orchestrator as orchestrator_module
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.session_manager import Session


class _AsyncOnlyGraph:
    """Fake graph that proves the orchestrator uses LangGraph's async API."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    def invoke(self, *_: object, **__: object) -> None:
        pytest.fail("The synchronous LangGraph invoke API must not be used.")

    async def ainvoke(self, state: dict, config: dict) -> dict:
        self.calls.append((state, config))
        return {
            "messages": state["messages"] + [
                {
                    "role": "assistant",
                    "name": "Alex (Training Planner)",
                    "content": "Alex (Training Planner): Welcome!",
                    "metadata": {"nutrition_profile_required": True},
                }
            ]
        }


@pytest.mark.asyncio
async def test_process_message_invokes_async_graph_api() -> None:
    graph = _AsyncOnlyGraph()
    orchestrator = AgentOrchestrator()
    orchestrator.graph = graph
    session = Session(
        session_id="chat_0123456789abcdef",
        user_id=42,
        profile={"name": "Taylor", "fitness_goal": "strength", "fitness_level": "intermediate"},
    )

    response = await orchestrator.process_message(session, "hi")

    assert response == "Alex (Training Planner): Welcome!"
    assert graph.calls == [
        (
            {
                "messages": [{"role": "user", "content": "You: hi"}],
                "volley_msg_left": 1,
                "next_agent": None,
                "user_profile": {
                    "user_id": 42,
                    "name": "Taylor",
                    "goal": "strength",
                    "fitness_level": "intermediate",
                },
            },
            {"recursion_limit": 50},
        )
    ]


@pytest.mark.asyncio
async def test_process_message_with_metadata_preserves_specialist_metadata() -> None:
    graph = _AsyncOnlyGraph()
    orchestrator = AgentOrchestrator()
    orchestrator.graph = graph
    session = Session(
        session_id="chat_0123456789abcdef",
        user_id=42,
        profile={},
    )

    response, metadata = await orchestrator.process_message_with_metadata(session, "hi")

    assert response == "Alex (Training Planner): Welcome!"
    assert metadata == {"nutrition_profile_required": True}


@pytest.mark.asyncio
async def test_process_message_excludes_historical_specialist_responses() -> None:
    class _HistoryPreservingGraph:
        async def ainvoke(self, state: dict, config: dict) -> dict:
            assert config == {"recursion_limit": 50}
            return {
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "name": "Sam (Nutrition Advisor)",
                        "content": "Sam (Nutrition Advisor): Greek yogurt protein bowl — 430 calories, 40 g protein.",
                        "metadata": {"nutrition_status": "ok"},
                    }
                ]
            }

    orchestrator = AgentOrchestrator()
    orchestrator.graph = _HistoryPreservingGraph()
    session = Session(
        session_id="chat_0123456789abcdef",
        user_id=42,
        profile={},
    )
    session.messages = [
        {"role": "user", "content": "I want a strength plan."},
        {
            "role": "assistant",
            "name": "Alex (Training Planner)",
            "content": "Alex (Training Planner): What days can you train this week?",
        },
    ]

    response, metadata = await orchestrator.process_message_with_metadata(
        session,
        "Give me a high-protein breakfast under 500 calories.",
    )

    assert response == "Sam (Nutrition Advisor): Greek yogurt protein bowl — 430 calories, 40 g protein."
    assert "Alex (Training Planner)" not in response
    assert metadata == {"nutrition_status": "ok"}


@pytest.mark.asyncio
async def test_process_message_stream_forwards_custom_tokens_and_persists_completed_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StreamingGraph:
        async def astream(self, state: dict, config: dict, stream_mode: list[str]):
            assert config == {"recursion_limit": 50}
            assert stream_mode == ["custom", "values"]
            yield "custom", {"type": "token", "token": "Welcome"}
            yield "custom", {"type": "token", "token": "!"}
            yield "values", {
                "messages": state["messages"] + [{
                    "role": "assistant",
                    "name": "Alex (Training Planner)",
                    "content": "Alex (Training Planner): Welcome!",
                    "metadata": {"source": "stream"},
                }],
                "next_agent": "training_planner",
                "volley_msg_left": 0,
            }

    persisted: dict[str, object] = {}

    async def update_session(**kwargs: object) -> bool:
        persisted.update(kwargs)
        return True

    monkeypatch.setattr(orchestrator_module.session_manager, "update_session", update_session)
    orchestrator = AgentOrchestrator()
    orchestrator.streaming_graph = _StreamingGraph()
    session = Session(
        session_id="chat_0123456789abcdef",
        user_id=42,
        profile={"name": "Taylor"},
    )

    events = [
        event async for event in orchestrator.process_message_stream(session, "hello")
    ]

    assert events == [
        {"type": "token", "token": "Welcome"},
        {"type": "token", "token": "!"},
        {"type": "complete", "text": "Alex (Training Planner): Welcome!", "metadata": {"source": "stream"}},
    ]
    assert persisted["messages"] == [
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "name": "Alex (Training Planner)",
            "content": "Alex (Training Planner): Welcome!",
            "metadata": {"source": "stream"},
        },
    ]