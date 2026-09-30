from datetime import UTC, datetime

from app.api.schemas.dashboard import TrainingWorkoutResponse


def test_training_workout_response_defaults_reused_to_false():
    response = TrainingWorkoutResponse(
        status="ready",
        title="Today’s personalized workout",
        workout_text="Warm-up",
        recovery_status="green",
        generated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert response.reused is False
    assert response.recovery_note is None
