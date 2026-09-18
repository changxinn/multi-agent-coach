from agents.summarizer import summarize_locally

from .schemas import SummarizeRequest, SummarizeResponse


def summarize(payload: SummarizeRequest) -> SummarizeResponse:
    state = {
        "messages": payload.messages,
        "user_profile": payload.user_profile,
        "agent_results": payload.agent_results,
        "safety_flags": payload.safety_flags,
        "session_id": payload.session_id,
        "summary_kind": payload.summary_kind,
    }
    return SummarizeResponse(summary=summarize_locally(state, payload.progress_text))
