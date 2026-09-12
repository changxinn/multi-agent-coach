"""
Chat routes for multi-agent conversations.
"""
import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
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
from app.services.chat_history_service import (
    ChatHistoryService,
    ChatSessionNotFoundError,
    ChatTurnConflictError,
)
from app.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
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
    if not isinstance(idempotency_key, str):
        idempotency_key = None

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

    try:
        history = ChatHistoryService(db)
        session = await history.build_view(user_id, request.session_id, profile)
    except ChatSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    user_message = request.messages[0].content
    if idempotency_key is not None:
        _validate_idempotency_key(idempotency_key)
        try:
            session, turn, claimed = await history.claim_turn(
                user_id,
                request.session_id,
                idempotency_key,
                _fingerprint(user_message),
                user_message,
            )
        except ChatTurnConflictError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        if not claimed:
            return _chat_response(session.session_id, turn.response_text or "", turn.response_metadata)
    else:
        await history.append_user_message(session, user_message)

    orchestrator = get_orchestrator()
    try:
        chat_context = await history.nutrition_context(session)
        response_text, response_metadata = await orchestrator.process_message_with_metadata(
            session=session, user_message=user_message, request_summary=False, chat_context=chat_context,
        )
        if idempotency_key is not None:
            await history.complete_turn(
                user_id, request.session_id, idempotency_key, response_text, response_metadata
            )
        else:
            await history.append_assistant_message(session, response_text, None, response_metadata)
    except Exception:
        if idempotency_key is not None:
            await history.fail_turn(user_id, request.session_id, idempotency_key)
        raise
    return _chat_response(session.session_id, response_text, response_metadata)


@router.get("/chat/stream")
async def chat_stream(
    message: str = Query(..., min_length=1, max_length=4000, description="User message"),
    session_id: str = Query(..., pattern=r"^chat_[a-f0-9]{32}$", description="Session ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
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
    if not isinstance(idempotency_key, str):
        idempotency_key = None

    # Get user profile
    profile_service = UserProfileService(db)
    try:
        profile = await profile_service.get_user_profile(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    try:
        history = ChatHistoryService(db)
        history = ChatHistoryService(db)
        session = await history.build_view(user_id, session_id, profile)
    except ChatSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    replay_text: str | None = None
    replay_metadata: dict | None = None
    if idempotency_key is not None:
        _validate_idempotency_key(idempotency_key)
        try:
            session, turn, claimed = await history.claim_turn(
                user_id, session_id, idempotency_key, _fingerprint(message), message
            )
        except ChatTurnConflictError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        if not claimed:
            replay_text = turn.response_text or ""
            replay_metadata = turn.response_metadata

    async def generate():
        response_parts: list[str] = []
        try:
            if replay_text is not None:
                yield f"data: {json.dumps({'token': replay_text, 'session_id': session_id, 'is_complete': False})}\n\n"
                yield f"data: {json.dumps({'token': '', 'session_id': session_id, 'is_complete': True, 'metadata': replay_metadata})}\n\n"
                return
            logger.info("Processing message through multi-agent system: %s", message)
            if idempotency_key is None:
                await history.append_user_message(session, message)
            # Get orchestrator
            orchestrator = get_orchestrator()
            chat_context = await history.nutrition_context(session)
            
            async for event in orchestrator.process_message_stream(
                session=session,
                user_message=message,
                chat_context=chat_context,
            ):
                if event["type"] == "token":
                    response_parts.append(event["token"])
                    yield f"data: {json.dumps({'token': event['token'], 'session_id': session_id, 'is_complete': False})}\n\n"
                elif event["type"] == "complete":
                    response_text = event.get("text") or "".join(response_parts)
                    if idempotency_key is not None:
                        await history.complete_turn(
                            user_id, session_id, idempotency_key, response_text, event.get("metadata")
                        )
                    else:
                        await history.append_assistant_message(session, response_text, None, event.get("metadata"))
                    yield f"data: {json.dumps({'token': '', 'session_id': session_id, 'is_complete': True, 'metadata': event.get('metadata')})}\n\n"
            logger.info("Multi-agent streaming completed")

        except Exception as e:
            logger.exception("Streaming error")
            if idempotency_key is not None:
                await history.fail_turn(user_id, session_id, idempotency_key)
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


def _validate_idempotency_key(value: str) -> None:
    try:
        uuid.UUID(value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key must be a UUID",
        ) from error


def _fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _chat_response(session_id: str, message: str, metadata: dict | None) -> ChatResponse:
    return ChatResponse(message=message, session_id=session_id, model="gpt-5-nano", metadata=metadata)


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

    try:
        profile = await UserProfileService(db).get_user_profile(user_id)
        session = await ChatHistoryService(db).build_view(user_id, request.session_id, profile)
    except (ValueError, ChatSessionNotFoundError):
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
    db: AsyncSession = Depends(get_db),
):
    """
    Clear chat history for a session.

    **Authentication Required**: JWT token in Authorization header
    """
    try:
        await ChatHistoryService(db).clear(current_user["id"], session_id)
        return {"status": "cleared", "session_id": session_id}
    except ChatSessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
