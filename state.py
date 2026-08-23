import operator
from typing import Annotated, TypedDict


class State(TypedDict):
    """
    Shared state for the fitness coaching LangGraph workflow.
    """

    messages: Annotated[list, operator.add]
    volley_msg_left: int
    next_agent: str | None
    user_profile: dict
