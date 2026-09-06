import hashlib

import pytest

from app.services.nutrition_rollout import (
    is_nutrition_agent_enabled_for_user,
    nutrition_rollout_bucket,
    validate_rollout_percent,
)


def expected_bucket(user_id: int) -> int:
    digest = hashlib.sha256(str(user_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 100


@pytest.mark.parametrize("user_id", [1, 2, 42, 1001, 987654321])
def test_nutrition_rollout_bucket_is_stable_sha256(user_id):
    assert nutrition_rollout_bucket(user_id) == expected_bucket(user_id)
    assert nutrition_rollout_bucket(user_id) == nutrition_rollout_bucket(user_id)


def test_rollout_zero_routes_no_users():
    for user_id in range(1, 25):
        assert is_nutrition_agent_enabled_for_user(user_id, 0) is False


def test_rollout_hundred_routes_all_users():
    for user_id in range(1, 25):
        assert is_nutrition_agent_enabled_for_user(user_id, 100) is True


@pytest.mark.parametrize("percent", [10, 50])
def test_rollout_uses_bucket_boundary(percent):
    for user_id in range(1, 50):
        assert is_nutrition_agent_enabled_for_user(user_id, percent) == (
            nutrition_rollout_bucket(user_id) < percent
        )


@pytest.mark.parametrize("percent", [-1, 101])
def test_rollout_percent_validation_rejects_out_of_range_values(percent):
    with pytest.raises(ValueError):
        validate_rollout_percent(percent)


@pytest.mark.parametrize("percent", [10.5, True, "10"])
def test_rollout_percent_validation_rejects_invalid_types(percent):
    with pytest.raises(TypeError):
        validate_rollout_percent(percent)


@pytest.mark.parametrize("user_id", [0, -1, 1.5, False, "1"])
def test_rollout_bucket_rejects_invalid_user_ids(user_id):
    with pytest.raises(ValueError):
        nutrition_rollout_bucket(user_id)
