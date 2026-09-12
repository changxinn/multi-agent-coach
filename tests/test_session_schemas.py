"""Regression coverage for session response serialization."""

from app.api.schemas.session import (
    SessionDetailsResponse,
    SessionResponse,
)

PROFILE = {
    "user_id": 1,
    "name": "System Admin",
    "fitness_goal": "general fitness",
    "fitness_level": "beginner",
    "weight_kg": None,
    "height_cm": None,
    "age": None,
}


def test_session_response_accepts_profile_with_nullable_measurements() -> None:
    response = SessionResponse(
        session_id="chat_0123456789abcdef0123456789abcdef",
        user_id=1,
        created=True,
        profile=PROFILE,
    )

    assert response.profile.model_dump() == PROFILE


def test_session_details_response_accepts_profile_with_nullable_measurements() -> None:
    response = SessionDetailsResponse(
        session_id="chat_0123456789abcdef0123456789abcdef",
        user_id=1,
        profile=PROFILE,
        messages=[],
        created_at="2026-09-11T20:51:35+00:00",
        last_activity="2026-09-11T20:51:35+00:00",
    )

    assert response.profile.model_dump() == PROFILE