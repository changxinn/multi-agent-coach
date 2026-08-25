"""
Session management routes.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.routes.auth import get_current_user
from app.api.schemas.session import (
    SessionCreateRequest,
    SessionResponse,
    SessionDetailsResponse,
    SessionClearRequest,
)
from app.services.session_manager import session_manager, get_session_manager
from app.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/session", response_model=SessionResponse)
async def create_session(
    request: Optional[SessionCreateRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new chat session.

    If session_id is provided, validates format and creates session with that ID.
    If not provided, auto-generates a session ID.

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

    # Create session
    session_mgr = get_session_manager()
    session_id = request.session_id if request else None

    try:
        session = await session_mgr.create_session(
            user_id=user_id,
            profile=profile,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

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
):
    """
    Get session details and message history.

    **Authentication Required**: JWT token in Authorization header
    """
    session_mgr = get_session_manager()

    try:
        session = await session_mgr.get_session(session_id, current_user["id"])
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's session",
        )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionDetailsResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        profile=session.profile,
        messages=session.messages,
        created_at=session.created_at.isoformat(),
        last_activity=session.last_activity.isoformat(),
    )


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a session completely.

    **Authentication Required**: JWT token in Authorization header
    """
    session_mgr = get_session_manager()

    try:
        success = await session_mgr.delete_session(session_id, current_user["id"])

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        return {"status": "deleted", "session_id": session_id}

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's session",
        )


@router.post("/session/clear")
async def clear_session(
    request: SessionClearRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Clear session messages (keeps session alive).

    **Authentication Required**: JWT token in Authorization header
    """
    session_mgr = get_session_manager()

    try:
        success = await session_mgr.clear_session(request.session_id, current_user["id"])

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        return {"status": "cleared", "session_id": request.session_id}

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's session",
        )
