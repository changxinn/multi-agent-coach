"""Live service fixtures; collection never makes HTTP or model calls."""

import os

import httpx
import pytest
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams


@pytest.fixture(scope="session")
def api():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.fail("Set OPENAI_API_KEY before running live evaluations.")
    token = os.getenv("INTERNAL_SERVICE_TOKEN")
    if not token:
        pytest.fail("Set INTERNAL_SERVICE_TOKEN to match the services.")
    with httpx.Client(
        headers={"X-Internal-Service-Token": token}, timeout=180, trust_env=False
    ) as client:
        yield client


@pytest.fixture
def route(api):
    def call(text, history=None):
        url = os.getenv("HEAD_COACH_URL", "http://localhost:8002")
        response = api.post(
            f"{url}/v1/head-coach/route",
            json={
                "messages": (history or []) + [{"role": "user", "content": text}],
                "user_profile": {
                    "goal": "general fitness",
                    "fitness_level": "beginner",
                },
                "volley_msg_left": 2,
            },
        )
        response.raise_for_status()
        return response.json()

    return call


@pytest.fixture
def summarize(api):
    def call(payload):
        url = os.getenv("SUMMARIZER_URL", "http://localhost:8003")
        response = api.post(f"{url}/v1/summarizer/summarize", json=payload)
        response.raise_for_status()
        data = response.json()
        assert data["agent"] == "summarizer"
        assert isinstance(data["summary"], str) and data["summary"].strip()
        # A model failure must not silently pass as a successful live evaluation.
        assert not data["summary"].startswith("=== SESSION SUMMARY ===")
        assert not data["summary"].startswith("Easy-to-moderate session today")
        return data["summary"]

    return call


@pytest.fixture
def judge():
    def make(name, criteria, threshold=0.8):
        return GEval(
            name=name,
            criteria=criteria,
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            model=os.getenv("DEEPEVAL_JUDGE_MODEL", "gpt-4.1-mini"),
            threshold=threshold,
            async_mode=False,
        )

    return make
