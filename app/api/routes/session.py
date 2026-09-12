"""
Session management routes.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.api.routes.auth import get_current_user
from app.api.schemas.session import (
    SessionClearRequest,
    SessionDetailsResponse,
    SessionResponse,
)
from app.db.database import get_db
from app.services.chat_history_service import (
    ChatHistoryService,
    ChatSessionNotFoundError,
)
from app.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/session", response_model=SessionResponse)
async def create_session(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new chat session.

    The server allocates an unguessable session ID. Client-provided IDs are not accepted.

    **Authentication Required**: JWT token in Authorization header
    """
    user_id = current_user["id"]

    # Get user profile from database
    profile_service = UserProfileService(db)
    try:
        profile = await profile_service.get_user_profile(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    session = await ChatHistoryService(db).create_session(user_id)

    return SessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        created=True,
        profile=profile,
        message_count=0,
    )


@router.get("/session/{session_id}", response_model=SessionDetailsResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get session details and message history.

    **Authentication Required**: JWT token in Authorization header
    """
    try:
        profile = await UserProfileService(db).get_user_profile(current_user["id"])
        session = await ChatHistoryService(db).details(current_user["id"], session_id, profile)
    except (ValueError, ChatSessionNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionDetailsResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        profile=session.profile,
        messages=session.messages,
        created_at=session.record.created_at.isoformat(),
        last_activity=session.record.updated_at.isoformat(),
    )


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a session completely.

    **Authentication Required**: JWT token in Authorization header
    """
    try:
        await ChatHistoryService(db).delete(current_user["id"], session_id)
        return {"status": "deleted", "session_id": session_id}
    except ChatSessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/session/clear")
async def clear_session(
    request: SessionClearRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clear session messages (keeps session alive).

    **Authentication Required**: JWT token in Authorization header
    """
    try:
        await ChatHistoryService(db).clear(current_user["id"], request.session_id)
        return {"status": "cleared", "session_id": request.session_id}
    except ChatSessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
