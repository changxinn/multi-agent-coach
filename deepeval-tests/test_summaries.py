import json

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase


@pytest.mark.parametrize("kind", ["session", "daily"])
def test_summary_quality(summarize, judge, kind):
    payload = {
        "summary_kind": kind,
        "user_profile": {"goal": "build strength", "fitness_level": "beginner"},
        "messages": [
            {"role": "user", "content": "I slept 5 hours and feel tired today."},
            {
                "role": "assistant",
                "content": "Keep training light today, prioritize sleep tonight, "
                "and include protein and carbs in your meals.",
            },
        ],
        "progress_text": "One 20-minute walk logged today. No strength workout logged.",
    }
    output = summarize(payload)
    if kind == "daily":
        assert len(output.split()) <= 70
        assert "Recovery emphasis:" in output
        assert "Fuel:" in output
        assert not output.lower().startswith("your day at a glance")
        assert output.endswith("You got this bestie!")
    else:
        # The service appends the original progress text after the generated summary.
        assert len(output.split("\n\n---\n\n", 1)[0].split()) < 200
    assert_test(
        LLMTestCase(
            input=json.dumps(payload),
            actual_output=output,
            expected_output="A concise, encouraging summary reflecting short sleep, "
            "light training and recovery. Any activity described as completed must "
            "match the logged walk. No invented workouts, meals, or health facts. "
            "New suggestions are allowed if clearly presented as advice.",
        ),
        [
            judge(
                "Summary faithfulness and usefulness",
                "Evaluate whether the summary follows the expected output, accurately "
                "reflects the supplied facts and gives relevant practical advice. "
                "Penalize fabricated accomplishments and advice contradicting fatigue.",
            )
        ],
    )
