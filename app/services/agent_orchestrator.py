"""
Agent orchestrator service for coordinating multi-agent conversations.

Integrates LangGraph workflow with FastAPI.
"""
import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Dict, List

from app.services.session_manager import Session, session_manager

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Orchestrates multi-agent conversations.

    Coordinates Head Coach (orchestrator) with specialist agents.
    """

    def __init__(self):
        self.graph = None
        self.streaming_graph = None
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

    async def _get_streaming_graph(self):
        """Lazy load the graph variant that emits safe, user-visible token events."""
        if self.streaming_graph is None:
            async with self._graph_lock:
                if self.streaming_graph is None:
                    from app.services.agent_service import build_streaming_api_graph

                    self.streaming_graph = build_streaming_api_graph()
                    logger.info("Streaming LangGraph initialized")
        return self.streaming_graph

    @staticmethod
    def _initial_state(session: Session, user_message: str) -> dict[str, Any]:
        """Build the common input state for synchronous and streaming graph runs."""
        user_profile = {
            "user_id": session.user_id,
            "name": session.profile.get("name", "Athlete"),
            "goal": session.profile.get("fitness_goal", "general fitness"),
            "fitness_level": session.profile.get("fitness_level", "beginner"),
        }
        return {
            "messages": session.messages + [
                {"role": "user", "content": f"You: {user_message}"}
            ],
            "volley_msg_left": 1,
            "next_agent": None,
            "user_profile": user_profile,
        }

    async def process_message(
        self,
        session: Session,
        user_message: str,
        request_summary: bool = False,
    ) -> str:
        response_text, _ = await self.process_message_with_metadata(
            session=session,
            user_message=user_message,
            request_summary=request_summary,
        )
        return response_text

    async def process_message_with_metadata(
        self,
        session: Session,
        user_message: str,
        request_summary: bool = False,
    ) -> tuple[str, dict[str, Any] | None]:
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

            initial_state = self._initial_state(session, user_message)
            input_message_count = len(initial_state["messages"])

            # Invoke graph through its async API because the API workflow
            # contains asynchronous specialist nodes.
            logger.info("Invoking LangGraph for user message")
            result = await graph.ainvoke(
                initial_state,
                {"recursion_limit": 50},
            )

            # State.messages uses LangGraph's additive reducer, so the graph result
            # includes the conversation supplied as input followed by messages
            # generated for this turn. Only return and persist the latter; otherwise
            # historical specialist replies are rendered again in the UI.
            generated_messages = result.get("messages", [])[input_message_count:]
            assistant_messages = [
                m for m in generated_messages
                if m.get("role") == "assistant"
            ]

            # Aggregate responses and expose the final specialist metadata to
            # structured API consumers.
            response_text = self._aggregate_responses(assistant_messages)
            response_metadata = assistant_messages[-1].get("metadata") if assistant_messages else None

            # If summary requested, generate it
            if request_summary:
                summary = await self._generate_summary(session, user_message)
                response_text = f"{response_text}\n\n---\n\n**Session Summary:**\n{summary}"

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

            logger.info(
                "Message processed successfully. Response length: %d chars",
                len(response_text),
            )

            return response_text, response_metadata

        except Exception as e:
            logger.error("Error processing message: %s", e, exc_info=True)
            return (
                "I apologize, but I encountered an error processing your request. "
                "Please try again.",
                None,
            )

    async def process_message_stream(
        self,
        session: Session,
        user_message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield real model text chunks and a final metadata event for one chat turn.

        The streaming graph emits custom events only after its specialist has identified
        the public ``Message:`` portion of the model output. This prevents internal
        ReAct tool instructions from reaching API clients.
        """
        graph = await self._get_streaming_graph()
        initial_state = self._initial_state(session, user_message)
        final_state: dict[str, Any] | None = None

        async for mode, payload in graph.astream(
            initial_state,
            {"recursion_limit": 50},
            stream_mode=["custom", "values"],
        ):
            if mode == "custom":
                if isinstance(payload, dict) and payload.get("type") == "token":
                    token = payload.get("token")
                    if isinstance(token, str) and token:
                        yield {"type": "token", "token": token}
            elif mode == "values" and isinstance(payload, dict):
                final_state = payload

        if final_state is None:
            raise RuntimeError("Streaming graph completed without a final state")

        input_message_count = len(initial_state["messages"])
        new_messages = final_state.get("messages", [])[input_message_count:]
        response_text = self._aggregate_responses(new_messages)
        metadata = next(
            (
                message.get("metadata")
                for message in reversed(new_messages)
                if isinstance(message, dict) and message.get("role") == "assistant"
            ),
            None,
        )

        await session_manager.update_session(
            session_id=session.session_id,
            user_id=session.user_id,
            messages=[
                {"role": "user", "content": user_message},
                *new_messages,
            ],
            agent_state={
                "last_agent": final_state.get("next_agent"),
                "volley_remaining": final_state.get("volley_msg_left", 0),
            },
        )
        yield {"type": "complete", "text": response_text, "metadata": metadata}

    def _aggregate_responses(self, messages: List[Dict[str, Any]]) -> str:
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
        by_agent: Dict[str, List[str]] = {}
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
                c.replace("You: ", "").strip()
                for c in contents
            ]
            section_content = " ".join(cleaned_contents)

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
            return summary

        except Exception as e:
            logger.error("Error generating summary: %s", e)
            return "Unable to generate summary at this time."


# Global singleton instance
orchestrator = AgentOrchestrator()


def get_orchestrator() -> AgentOrchestrator:
    """Get orchestrator singleton."""
    return orchestrator
