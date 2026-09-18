"""HTTP client for the Summarizer microservice. Used only by the API process."""

from __future__ import annotations

import os
from typing import Any

import httpx


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def should_call_summarizer_service() -> bool:
    if _flag("SUMMARIZER_SERVICE_MODE"):
        return False
    return _flag("USE_SUMMARIZER_SERVICE")


class SummarizerClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("SUMMARIZER_URL", "http://localhost:8003").rstrip("/")
        self.token = os.getenv("INTERNAL_SERVICE_TOKEN", "")

    def summarize(self, state: dict[str, Any], progress: str) -> str:
        if not self.token:
            raise RuntimeError(
                "INTERNAL_SERVICE_TOKEN is required for the Summarizer service"
            )

        response = httpx.post(
            f"{self.base_url}/v1/summarizer/summarize",
            headers={"X-Internal-Service-Token": self.token},
            json={
                "messages": state.get("messages", []),
                "user_profile": state.get("user_profile", {}),
                "agent_results": state.get("agent_results", []),
                "safety_flags": state.get("safety_flags", []),
                "progress_text": progress,
                "session_id": state.get("session_id"),
                "summary_kind": state.get("summary_kind", "session"),
            },
            timeout=30,
        )
        response.raise_for_status()
        return str(response.json()["summary"])
