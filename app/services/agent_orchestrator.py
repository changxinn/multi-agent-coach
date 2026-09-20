"""
Agent orchestrator service for coordinating multi-agent conversations.

Integrates LangGraph workflow with FastAPI.
"""

import asyncio
import logging
from typing import Any

from app.services.chat_response import new_assistant_messages, strip_speaker_prefix
from app.services.session_manager import Session, session_manager

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Orchestrates multi-agent conversations.

    Coordinates Head Coach (orchestrator) with specialist agents.
    """

    def __init__(self):
        self.graph = None
        self._graph_lock = asyncio.Lock()

    async def _get_graph(self):
        """Lazy load LangGraph to avoid import errors."""
        if self.graph is None:
            async with self._graph_lock:
                if self.graph is None:
                    from app.services.agent_service import build_api_graph

                    self.graph = build_api_graph()
                    logger.info("LangGraph initialized")
        return self.graph

    async def process_message(
        self,
        session: Session,
        user_message: str,
        request_summary: bool = False,
    ) -> str:
        """
        Process user message through multi-agent system.

        Flow:
        1. Add user message to session
        2. Build LangGraph state
        3. Invoke graph (orchestrator → specialist → ...)
        4. Collect and aggregate responses
        5. Update session
        6. Return response

        Args:
            session: User session
            user_message: User's message
            request_summary: If True, generate summary after response

        Returns:
            Aggregated response text
        """
        try:
            # Get graph
            graph = await self._get_graph()

            # Build initial state
            # Convert session profile to LangGraph State format
            user_profile = {
                "user_id": session.user_id,
                "name": session.profile.get("name", "Athlete"),
                "goal": session.profile.get("fitness_goal", "general fitness"),
                "fitness_level": session.profile.get("fitness_level", "beginner"),
            }

            # Prepare messages for LangGraph
            messages = session.messages + [
                {"role": "user", "content": f"You: {user_message}"}
            ]

            initial_state = {
                "messages": messages,
                "volley_msg_left": 1,
                "next_agent": None,
                "user_profile": user_profile,
            }

            # Invoke graph
            logger.info("Invoking LangGraph for user message")
            result = await asyncio.to_thread(
                graph.invoke,
                initial_state,
                {"recursion_limit": 50},
            )

            # Extract assistant messages from result
            assistant_messages = new_assistant_messages(
                session.messages,
                result.get("messages", []),
            )

            # Aggregate responses
            response_text = self._aggregate_responses(assistant_messages)
            if not response_text.strip():
                response_text = "I'm here. Ask me about training, food, or recovery whenever you're ready."

            # If summary requested, generate it
            if request_summary:
                summary = await self._generate_summary(session, user_message)
                response_text = (
                    f"{response_text}\n\n---\n\n**Session Summary:**\n{summary}"
                )

            # Update session with new messages
            new_messages = [
                {"role": "user", "content": user_message},
            ] + assistant_messages

            await session_manager.update_session(
                session_id=session.session_id,
                user_id=session.user_id,
                messages=new_messages,
                agent_state={
                    "volley_msg_left": result.get("volley_msg_left", 0),
                },
            )

            from app.services.coach_event_store import (
                persist_routing_event,
                resolve_persisted_routing_agent,
            )

            await persist_routing_event(
                user_id=session.user_id,
                session_id=session.session_id,
                next_agent=resolve_persisted_routing_agent(result),
                routing_reason=result.get("routing_reason"),
                needs_clarification=bool(result.get("needs_clarification")),
                safety_flags=result.get("safety_flags") or [],
                user_message=user_message,
            )

            logger.info(
                "Message processed successfully. Response length: %d chars",
                len(response_text),
            )

            return response_text

        except Exception:
            logger.exception("Error processing message")
            return (
                "I apologize, but I encountered an error processing your request. "
                "Please try again."
            )

    async def process_message_stream(
        self,
        session: Session,
        user_message: str,
        request_summary: bool = False,
    ):
        """
        Process user message through multi-agent system with streaming.

        Args:
            session: User session
            user_message: User's message
            request_summary: If True, generate summary after response

        Yields:
            Individual tokens/characters for streaming
        """
        try:
            # Get the full response first
            response_text = await self.process_message(
                session=session,
                user_message=user_message,
                request_summary=request_summary,
            )

            # Stream character by character
            for char in response_text:
                yield char

        except Exception as e:
            logger.exception("Error in streaming")
            # Yield error message
            error_text = f"I apologize, but I encountered an error: {e!s}"
            for char in error_text:
                yield char

    def _aggregate_responses(self, messages: list[dict[str, Any]]) -> str:
        """
        Combine multiple agent messages into single response.

        Args:
            messages: List of assistant messages

        Returns:
            Aggregated response text
        """
        if not messages:
            return ""

        # Group by agent name
        by_agent: dict[str, list[str]] = {}
        for msg in messages:
            agent_name = msg.get("name", "Coach")
            content = msg.get("content", "").strip()

            if agent_name not in by_agent:
                by_agent[agent_name] = []

            if content:
                by_agent[agent_name].append(content)

        # Format as markdown with sections
        sections = []
        for agent_name, contents in by_agent.items():
            # Clean up content (remove "You: " prefix if present)
            cleaned_contents = [
                strip_speaker_prefix(c.replace("You: ", "")) for c in contents
            ]
            cleaned_contents = [c for c in cleaned_contents if c]
            section_content = " ".join(dict.fromkeys(cleaned_contents))

            # Add agent name as header if multiple agents
            if len(by_agent) > 1:
                sections.append(f"### {agent_name}\n{section_content}")
            else:
                sections.append(section_content)

        return "\n\n".join(sections)

    async def _generate_summary(
        self,
        session: Session,
        current_message: str,
    ) -> str:
        """
        Generate session summary using summarizer agent.

        Args:
            session: User session
            current_message: Current user message

        Returns:
            Summary text
        """
        try:
            # Import summarizer directly
            from agents.summarizer import summarizer as summarizer_agent

            # Prepare state for summarizer
            user_profile = {
                "name": session.profile.get("name", "Athlete"),
                "goal": session.profile.get("fitness_goal", "general fitness"),
                "fitness_level": session.profile.get("fitness_level", "beginner"),
            }

            state = {
                "messages": session.messages,
                "volley_msg_left": 0,
                "next_agent": None,
                "user_profile": user_profile,
            }

            # Call summarizer
            summary = summarizer_agent(state)

            logger.info("Generated session summary")
            from app.services.coach_event_store import persist_summary

            await persist_summary(
                user_id=session.user_id,
                session_id=session.session_id,
                summary_type="session",
                summary_text=summary,
            )
            return summary

        except Exception as e:
            logger.error("Error generating summary: %s", e)
            return "Unable to generate summary at this time."


# Global singleton instance
orchestrator = AgentOrchestrator()


def get_orchestrator() -> AgentOrchestrator:
    """Get orchestrator singleton."""
    return orchestrator
