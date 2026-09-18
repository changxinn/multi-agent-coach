"""
Agents for the fitness coaching multi-agent system.

Export callables used as LangGraph nodes. Keep specialist lazy so Head Coach
and Summarizer images do not import teammate tool packages at startup.
"""

from .orchestrator import orchestrator
from .summarizer import summarizer

__all__ = ["orchestrator", "specialist", "summarizer"]


def __getattr__(name):
    if name == "specialist":
        from .specialist import specialist

        return specialist
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
