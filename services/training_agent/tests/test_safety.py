from services.training_agent.app.service import TrainingService


def test_red_and_escalate_are_hard_no_training_states():
    for recovery_status in ("red", "escalate"):
        status, _, workout_text = TrainingService.safety(recovery_status)
        assert status == "recovery_adjusted"
        assert workout_text is not None


def test_amber_daily_workout_is_volume_and_intensity_adjusted():
    text = TrainingService._workout_text({}, "amber")
    assert "2 rounds" in text
    assert "(RPE) 6-7" in text
