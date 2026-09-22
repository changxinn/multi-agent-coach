from unittest.mock import AsyncMock, Mock

import pytest

from app.db.models import User, UserFitnessProfile
from app.db.repositories.user_repo import UserRepository


@pytest.mark.asyncio
async def test_update_fitness_profile_updates_existing_profile():
    db = AsyncMock()
    db.add = Mock()
    profile = UserFitnessProfile(user_id=9, fitness_goal="general fitness")
    result = Mock()
    result.scalar_one_or_none.return_value = profile
    db.execute.return_value = result
    repository = UserRepository(db)
    repository.get_by_id = AsyncMock(return_value=Mock(spec=User, id=9))

    updated_profile = await repository.update_fitness_profile(
        user_id=9, age=31, weight_kg=72.25, height_cm=180.5
    )

    assert updated_profile is profile
    assert profile.age == 31
    assert profile.weight_kg == 72.25
    assert profile.height_cm == 180.5
    db.add.assert_not_called()
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(profile)


@pytest.mark.asyncio
async def test_update_fitness_profile_creates_missing_profile():
    db = AsyncMock()
    db.add = Mock()
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    repository = UserRepository(db)
    repository.get_by_id = AsyncMock(return_value=Mock(spec=User, id=9))

    profile = await repository.update_fitness_profile(user_id=9, age=31)

    assert profile.user_id == 9
    assert profile.age == 31
    db.add.assert_called_once_with(profile)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(profile)