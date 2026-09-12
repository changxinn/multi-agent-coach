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


def test_strength_update_after_lunch_request_deterministically_revises_lunch(monkeypatch) -> None:
    monkeypatch.setattr(
        orchestrator_module,
        "ChatOpenAI",
        lambda **_: (_ for _ in ()).throw(AssertionError("LLM routing must not run")),
    )

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [
                {"role": "user", "content": "You: Give me a lunch option."},
                {"role": "assistant", "content": "Sam: Grilled chicken salad with quinoa."},
                {"role": "user", "content": "You: I also did strength training earlier."},
            ],
            "user_profile": {},
        }
    )

    assert result == {
        "next_agent": "nutrition_advisor",
        "nutrition_follow_up": {
            "nutrition_follow_up": "revise_recent_meal",
            "activity_type": "resistance",
        },
        "volley_msg_left": 0,
    }


def test_cardio_update_after_lunch_request_deterministically_revises_lunch(monkeypatch) -> None:
    monkeypatch.setattr(
        orchestrator_module,
        "ChatOpenAI",
        lambda **_: (_ for _ in ()).throw(AssertionError("LLM routing must not run")),
    )

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [
                {"role": "user", "content": "You: Give me a lunch option."},
                {"role": "assistant", "content": "Sam: Grilled chicken salad with quinoa."},
                {"role": "user", "content": "You: I did cardio earlier."},
            ],
            "user_profile": {},
        }
    )

    assert result["next_agent"] == "nutrition_advisor"
    assert result["nutrition_follow_up"] == {
        "nutrition_follow_up": "revise_recent_meal",
        "activity_type": "endurance",
    }


def test_invalid_follow_up_classifier_falls_back_to_regular_routing(monkeypatch) -> None:
    class _LLM:
        def with_structured_output(self, _: object) -> object:
            return self

        def invoke(self, _: object) -> object:
            return orchestrator_module.RoutingDecision(
                route="specialist", specialist="training_planner"
            )

    monkeypatch.setattr(orchestrator_module, "ChatOpenAI", lambda **_: _LLM())

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [
                {"role": "user", "content": "You: Give me a dinner option."},
                {"role": "user", "content": "You: I exercised earlier."},
            ],
            "user_profile": {},
        }
    )

    assert result == {"next_agent": "training_planner", "volley_msg_left": 0}


def test_strength_training_update_without_meal_context_uses_llm_routing(monkeypatch) -> None:
    selected: list[object] = []

    class _LLM:
        def with_structured_output(self, _: object) -> object:
            return self

        def invoke(self, _: object) -> object:
            selected.append(True)
            return orchestrator_module.RoutingDecision(
                route="specialist", specialist="training_planner"
            )

    monkeypatch.setattr(orchestrator_module, "ChatOpenAI", lambda **_: _LLM())

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [{"role": "user", "content": "You: I also did strength training earlier."}],
            "user_profile": {},
        }
    )

    assert selected == [True]
    assert result == {"next_agent": "training_planner", "volley_msg_left": 0}


def test_explicit_workout_plan_after_dinner_request_does_not_inherit_nutrition_context(monkeypatch) -> None:
    class _LLM:
        def with_structured_output(self, _: object) -> object:
            return self

        def invoke(self, _: object) -> object:
            return orchestrator_module.RoutingDecision(
                route="specialist", specialist="training_planner"
            )

    monkeypatch.setattr(orchestrator_module, "ChatOpenAI", lambda **_: _LLM())

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [
                {"role": "user", "content": "You: Give me a dinner option."},
                {"role": "assistant", "content": "Sam: Lean beef with sweet potato."},
                {"role": "user", "content": "You: I did strength training earlier. Give me a workout plan."},
            ],
            "user_profile": {},
        }
    )

    assert result == {"next_agent": "training_planner", "volley_msg_left": 0}


def test_greeting_uses_llm_direct_head_coach_response(monkeypatch) -> None:
    called: list[object] = []

    class _LLM:
        def with_structured_output(self, schema: object) -> object:
            assert schema is orchestrator_module.RoutingDecision
            return self

        def invoke(self, _: object) -> object:
            called.append(True)
            return orchestrator_module.RoutingDecision(
                route="direct_response",
                response="Hi! What would you like help with today?",
            )

    monkeypatch.setattr(orchestrator_module, "ChatOpenAI", lambda **_: _LLM())

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [{"role": "user", "content": "You: hello"}],
            "user_profile": {},
        }
    )

    assert called == [True]
    assert result == {
        "messages": [
            {
                "role": "assistant",
                "name": "Head Coach",
                "content": "Head Coach: Hi! What would you like help with today?",
            }
        ],
        "next_agent": "human",
        "volley_msg_left": 0,
    }


def test_direct_response_strips_internal_routing_narration(monkeypatch) -> None:
    class _LLM:
        def with_structured_output(self, _: object) -> object:
            return self

        def invoke(self, _: object) -> object:
            return orchestrator_module.RoutingDecision(
                route="direct_response",
                response=(
                    "Routing decision: direct response. I’ll respond directly in chat. "
                    "What would you like help with next (training days, dinner options, "
                    "or a starter plan)?"
                ),
            )

    monkeypatch.setattr(orchestrator_module, "ChatOpenAI", lambda **_: _LLM())

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [{"role": "user", "content": "You: hello"}],
            "user_profile": {},
        }
    )

    assert result["messages"][0]["content"] == (
        "Head Coach: What would you like help with next (training days, dinner options, "
        "or a starter plan)?"
    )


def test_invalid_routing_decision_asks_for_clarification(monkeypatch) -> None:
    class _LLM:
        def with_structured_output(self, _: object) -> object:
            return self

        def invoke(self, _: object) -> object:
            return object()

    monkeypatch.setattr(orchestrator_module, "ChatOpenAI", lambda **_: _LLM())

    result = orchestrator_module.orchestrator(
        {
            "volley_msg_left": 1,
            "messages": [{"role": "user", "content": "You: I need help"}],
            "user_profile": {},
        }
    )

    assert result["next_agent"] == "human"
    assert result["messages"][0]["content"] == (
        "Head Coach: Hi! I can help with workout planning, nutrition, recovery, and progress "
        "tracking. What would you like to work on today?"
    )