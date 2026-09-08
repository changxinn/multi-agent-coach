"""
Chat routes for multi-agent conversations.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.api.routes.auth import get_current_user
from app.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SummaryRequest,
    SummaryResponse,
)
from app.db.database import get_db
from app.services.agent_orchestrator import get_orchestrator
from app.services.session_manager import get_session_manager
from app.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message to the multi-agent coaching system.

    The Head Coach orchestrates specialist agents (Training, Nutrition, Recovery)
    to provide a comprehensive response.

    **Authentication Required**: JWT token in Authorization header
    """
    user_id = current_user["id"]

    # Get user profile from database
    profile_service = UserProfileService(db)
    try:
        profile = await profile_service.get_user_profile(user_id)
    except ValueError as e:
        logger.error("User profile not found: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    # Get or create session
    session_mgr = get_session_manager()
    try:
        session = await session_mgr.get_or_create_session(
            session_id=request.session_id,
            user_id=user_id,
            profile=profile,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    # Process message through multi-agent system
    orchestrator = get_orchestrator()
    response_text, response_metadata = await orchestrator.process_message_with_metadata(
        session=session,
        user_message=request.messages[-1].content,
        request_summary=False,
    )

    return ChatResponse(
        message=response_text,
        session_id=session.session_id,
        model="gpt-5-nano",
        metadata=response_metadata,
    )


@router.get("/chat/stream")
async def chat_stream(
    message: str = Query(..., description="User message"),
    session_id: str = Query(..., description="Session ID"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream response from multi-agent system using Server-Sent Events (SSE).

    **Authentication Required**: JWT token in Authorization header

    **SSE Format**:
    ```
    data: {"token": "Hello", "session_id": "chat_abc123", "is_complete": false}
    data: {"token": "!", "session_id": "chat_abc123", "is_complete": false}
    data: {"token": "", "session_id": "chat_abc123", "is_complete": true, "metadata": {...}}
    ```
    """
    user_id = current_user["id"]

    # Get user profile
    profile_service = UserProfileService(db)
    try:
        profile = await profile_service.get_user_profile(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    # Get or create session
    session_mgr = get_session_manager()
    try:
        session = await session_mgr.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            profile=profile,
        )
    except (ValueError, PermissionError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Create async generator for SSE
    async def generate():
        try:
            logger.info("Processing message through multi-agent system: %s", message)
            
            # Get orchestrator
            orchestrator = get_orchestrator()
            
            async for event in orchestrator.process_message_stream(
                session=session,
                user_message=message,
            ):
                if event["type"] == "token":
                    yield f"data: {json.dumps({'token': event['token'], 'session_id': session_id, 'is_complete': False})}\n\n"
                elif event["type"] == "complete":
                    yield f"data: {json.dumps({'token': '', 'session_id': session_id, 'is_complete': True, 'metadata': event['metadata']})}\n\n"
            logger.info("Multi-agent streaming completed")

        except Exception as e:
            logger.exception("Streaming error")
            yield f"data: {json.dumps({'error': str(e), 'session_id': session_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/summary", response_model=SummaryResponse)
async def request_summary(
    request: SummaryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an on-demand session summary.

    Does not end the session - user can continue chatting after.

    **Authentication Required**: JWT token in Authorization header
    """
    user_id = current_user["id"]

    # Get session
    session_mgr = get_session_manager()
    session = await session_mgr.get_session(request.session_id, user_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Generate summary
    orchestrator = get_orchestrator()
    summary = await orchestrator._generate_summary(
        session=session,
        current_message="",
    )

    return SummaryResponse(
        summary=summary,
        session_id=session.session_id,
    )


@router.delete("/chat/history/{session_id}")
async def clear_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Clear chat history for a session.

    **Authentication Required**: JWT token in Authorization header
    """
    session_mgr = get_session_manager()

    try:
        success = await session_mgr.clear_session(session_id, current_user["id"])

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        return {"status": "cleared", "session_id": session_id}

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's session",
        )
