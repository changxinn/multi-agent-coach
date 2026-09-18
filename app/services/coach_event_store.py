"""Persist Head Coach and summarizer events without blocking the chat path."""

import logging

from app.db.database import AsyncSessionLocal
from app.db.repositories.coach_events_repo import CoachEventsRepository

logger = logging.getLogger(__name__)


def resolve_persisted_routing_agent(state: dict) -> str:
    """Use the specialist Head Coach picked, not the post-turn return to the user."""
    selected = state.get("selected_agent")
    if selected:
        return selected
    return state.get("next_agent") or "human"


async def persist_routing_event(
    *,
    user_id: int,
    session_id: str | None,
    next_agent: str | None,
    routing_reason: str | None,
    needs_clarification: bool,
    safety_flags: list[str] | None,
    user_message: str | None,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            repo = CoachEventsRepository(db)
            await repo.add_routing_event(
                user_id=user_id,
                session_id=session_id,
                next_agent=next_agent or "human",
                routing_reason=routing_reason,
                needs_clarification=needs_clarification,
                safety_flags=safety_flags or [],
                user_message=user_message,
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Could not persist Head Coach routing event: %s", exc)


async def persist_summary(
    *,
    user_id: int,
    session_id: str | None,
    summary_type: str,
    summary_text: str,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            repo = CoachEventsRepository(db)
            await repo.add_summary(
                user_id=user_id,
                session_id=session_id,
                summary_type=summary_type,
                summary_text=summary_text,
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Could not persist summarizer output: %s", exc)
