import operator
from typing import Annotated, NotRequired, TypedDict


class State(TypedDict):
    """
    Shared state for the fitness coaching LangGraph workflow.
    """

    messages: Annotated[list, operator.add]
    volley_msg_left: int
    next_agent: str | None
    user_profile: dict
    routing_reason: NotRequired[str]
    needs_clarification: NotRequired[bool]
    safety_flags: NotRequired[list]
    prompt_versions: NotRequired[dict]
