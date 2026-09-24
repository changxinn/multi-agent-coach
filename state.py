import operator
from typing import Annotated, NotRequired, TypedDict


class State(TypedDict):
    """
    Shared state for the fitness coaching LangGraph workflow.
    """

    messages: Annotated[list, operator.add]
    volley_msg_left: int
    next_agent: str | None
    selected_agent: NotRequired[str]
    user_profile: dict
    nutrition_context: NotRequired[dict]
    routing_reason: NotRequired[str]
    needs_clarification: NotRequired[bool]
    safety_flags: NotRequired[list]
    respectful_language_reminder: NotRequired[bool]
    prompt_versions: NotRequired[dict]
