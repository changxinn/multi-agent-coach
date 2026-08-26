"""
Session manager with in-memory storage and S3 archival.

Provides session management for chat conversations.
In-memory for development, Redis-ready for production.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import re
import json

from app.config import get_settings
from app.utils.s3_client import get_s3_client

logger = logging.getLogger(__name__)

settings = get_settings()

# Session ID validation pattern
SESSION_ID_PATTERN = re.compile(r"^chat_[a-f0-9]{16}$")


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format.

    Args:
        session_id: Session ID to validate

    Returns:
        True if valid format
    """
    return bool(SESSION_ID_PATTERN.match(session_id))


class Session:
    """Represents a chat session."""

    def __init__(self, session_id: str, user_id: int, profile: Dict[str, Any]):
        self.session_id = session_id
        self.user_id = user_id
        self.profile = profile
        self.messages: List[Dict[str, Any]] = []
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.agent_state: Dict[str, Any] = {}

    def is_expired(self) -> bool:
        """Check if session has expired."""
        expiry = self.last_activity + timedelta(hours=settings.SESSION_EXPIRY_HOURS)
        return datetime.utcnow() > expiry

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "profile": self.profile,
            "messages": self.messages,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "agent_state": self.agent_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        session = cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            profile=data.get("profile", {}),
        )
        session.messages = data.get("messages", [])
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.last_activity = datetime.fromisoformat(data["last_activity"])
        session.agent_state = data.get("agent_state", {})
        return session


class SessionManager:
    """
    In-memory session manager with S3 archival.

    Thread-safe with asyncio locks.
    Automatically archives messages to S3.
    """

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.lock = asyncio.Lock()
        self.s3_client = get_s3_client()

    async def create_session(
        self, user_id: int, profile: Dict[str, Any], session_id: Optional[str] = None
    ) -> Session:
        """
        Create new session for user.

        Args:
            user_id: User ID
            profile: User profile dict
            session_id: Optional session ID (must match pattern if provided)

        Returns:
            Created session
        """
        async with self.lock:
            if session_id:
                if not validate_session_id(session_id):
                    raise ValueError(
                        f"Invalid session ID format: {session_id}. "
                        f"Must match: {SESSION_ID_PATTERN.pattern}"
                    )
            else:
                # Auto-generate session ID
                import uuid
                session_id = f"chat_{uuid.uuid4().hex[:16]}"

            session = Session(session_id=session_id, user_id=user_id, profile=profile)
            self.sessions[session_id] = session

            logger.info("Created new session: %s for user: %d", session_id, user_id)
            return session

    async def get_or_create_session(
        self,
        session_id: str,
        user_id: int,
        profile: Dict[str, Any],
    ) -> Session:
        """
        Get existing session or create new one.

        Args:
            session_id: Session ID
            user_id: User ID
            profile: User profile dict

        Returns:
            Session
        """
        async with self.lock:
            # Validate session ID format
            if not validate_session_id(session_id):
                raise ValueError(
                    f"Invalid session ID format: {session_id}. "
                    f"Must match: {SESSION_ID_PATTERN.pattern}"
                )

            session = self.sessions.get(session_id)

            if not session:
                # Create new session
                session = Session(session_id=session_id, user_id=user_id, profile=profile)
                self.sessions[session_id] = session
                logger.info("Created new session: %s for user: %d", session_id, user_id)
            elif session.user_id != user_id:
                raise PermissionError("Cannot access another user's session")
            elif session.is_expired():
                # Remove expired session and create new one
                del self.sessions[session_id]
                session = Session(session_id=session_id, user_id=user_id, profile=profile)
                self.sessions[session_id] = session
                logger.info("Recreated expired session: %s for user: %d", session_id, user_id)

            return session

    async def get_session(self, session_id: str, user_id: int) -> Optional[Session]:
        """
        Get session by ID with authorization check.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Session or None if not found/expired

        Raises:
            PermissionError: If session belongs to different user
        """
        async with self.lock:
            if not validate_session_id(session_id):
                return None

            session = self.sessions.get(session_id)

            if not session:
                return None

            if session.user_id != user_id:
                raise PermissionError("Cannot access another user's session")

            if session.is_expired():
                del self.sessions[session_id]
                return None

            return session

    async def update_session(
        self,
        session_id: str,
        user_id: int,
        messages: List[Dict[str, Any]],
        agent_state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update session with new messages.

        Args:
            session_id: Session ID
            user_id: User ID
            messages: New messages to add
            agent_state: Optional agent state to update

        Returns:
            True if updated, False if session not found
        """
        async with self.lock:
            session = self.sessions.get(session_id)

            if not session:
                return False

            if session.user_id != user_id:
                raise PermissionError("Cannot access another user's session")

            # Add messages
            session.messages.extend(messages)
            session.last_activity = datetime.utcnow()

            if agent_state:
                session.agent_state = agent_state

            # Archive to S3 (non-blocking)
            if self.s3_client and self.s3_client.client:
                # Archive each message individually
                for message in messages:
                    asyncio.create_task(
                        self._archive_message(session, message)
                    )

            return True

    async def _archive_message(self, session: Session, message: Dict[str, Any]) -> bool:
        """
        Archive a single message to S3.

        Args:
            session: Session
            message: Message to archive

        Returns:
            True if successful
        """
        if not self.s3_client or not self.s3_client.client:
            return False

        try:
            await self.s3_client.save_message(
                user_id=str(session.user_id),
                session_id=session.session_id,
                message=message,
                timestamp=datetime.utcnow(),
            )
            return True
        except Exception as e:
            logger.error("Failed to archive message to S3: %s", e)
            return False

    async def clear_session(self, session_id: str, user_id: int) -> bool:
        """
        Clear session messages.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            True if cleared, False if not found
        """
        async with self.lock:
            session = self.sessions.get(session_id)

            if not session:
                return False

            if session.user_id != user_id:
                raise PermissionError("Cannot access another user's session")

            # Clear messages
            session.messages = []
            session.agent_state = {}
            session.last_activity = datetime.utcnow()

            # Delete from S3
            if self.s3_client and self.s3_client.client:
                asyncio.create_task(
                    self.s3_client.delete_session_history(
                        user_id=str(session.user_id),
                        session_id=session_id,
                    )
                )

            logger.info("Cleared session: %s", session_id)
            return True

    async def delete_session(self, session_id: str, user_id: int) -> bool:
        """
        Delete session completely.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        async with self.lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if session.user_id != user_id:
                    raise PermissionError("Cannot access another user's session")

                del self.sessions[session_id]

                # Delete from S3
                if self.s3_client and self.s3_client.client:
                    asyncio.create_task(
                        self.s3_client.delete_session_history(
                            user_id=str(session.user_id),
                            session_id=session_id,
                        )
                    )

                logger.info("Deleted session: %s", session_id)
                return True

            return False

    async def cleanup_expired_sessions(self) -> int:
        """
        Remove all expired sessions.

        Returns:
            Number of sessions removed
        """
        async with self.lock:
            expired = [
                session_id
                for session_id, session in self.sessions.items()
                if session.is_expired()
            ]

            for session_id in expired:
                del self.sessions[session_id]
                logger.info("Removed expired session: %s", session_id)

            return len(expired)

    async def start_cleanup_task(self, interval_hours: int = 1) -> asyncio.Task:
        """
        Start background cleanup task.

        Args:
            interval_hours: How often to run cleanup

        Returns:
            asyncio.Task
        """

        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_hours * 3600)
                try:
                    count = await self.cleanup_expired_sessions()
                    if count > 0:
                        logger.info("Cleanup removed %d expired sessions", count)
                except Exception as e:
                    logger.error("Cleanup task failed: %s", e)

        task = asyncio.create_task(cleanup_loop())
        logger.info("Started session cleanup task (interval: %dh)", interval_hours)
        return task


# Global singleton instance
session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Get session manager singleton."""
    return session_manager
