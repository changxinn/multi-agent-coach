"""Regression coverage for deterministic specialist routing."""

import importlib

orchestrator_module = importlib.import_module("agents.orchestrator")


def test_explicit_breakfast_request_routes_only_to_nutrition_without_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        orchestrator_module,
        "ChatOpenAI",
        lambda **_: (_ for _ in ()).throw(AssertionError("LLM routing must not run")),
    )

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "You: I train four days each week. Give me a high-protein breakfast under 500 calories.",
                }
            ],
            "user_profile": {},
        }
    )

    assert result == {"next_agent": "nutrition_advisor", "volley_msg_left": 0}