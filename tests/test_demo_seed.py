from unittest.mock import AsyncMock, Mock

import bcrypt
import pytest

from app.config import Settings
from app.db.demo_seed import DEMO_PASSWORD, DEMO_USERS, seed_demo_users
from app.db.models import User


def settings(*, seed_demo_users: bool) -> Settings:
    return Settings(
        JWT_SECRET_KEY="test-secret",
        DATABASE_URL="postgresql+asyncpg://user:password@localhost/test",
        OPENAI_API_KEY="",
        SEED_DEMO_USERS=seed_demo_users,
        NUTRITION_COMPATIBILITY_ADMIN_EMAIL="nutrition.admin@example.com",
    )


@pytest.mark.asyncio
async def test_seed_demo_users_is_disabled_by_default():
    db = AsyncMock()

    await seed_demo_users(db, settings(seed_demo_users=False))

    db.commit.assert_not_awaited()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_seed_demo_users_creates_users_with_distinct_profiles(monkeypatch):
    db = AsyncMock()
    repository = Mock()
    repository.get_by_email = AsyncMock(return_value=None)
    repository.create_user = AsyncMock(
        side_effect=[
            Mock(spec=User, id=1),
            Mock(spec=User, id=2),
            Mock(spec=User, id=3),
        ]
    )
    repository.update_fitness_profile = AsyncMock()
    monkeypatch.setattr("app.db.demo_seed.UserRepository", lambda _: repository)

    await seed_demo_users(db, settings(seed_demo_users=True))

    assert repository.get_by_email.await_args_list[0].args == (DEMO_USERS[0].email,)
    assert repository.get_by_email.await_args_list[1].args == (DEMO_USERS[1].email,)
    assert repository.get_by_email.await_args_list[2].args == (DEMO_USERS[2].email,)
    first_created = repository.create_user.await_args_list[0].kwargs
    assert first_created["email"] == DEMO_USERS[0].email
    assert bcrypt.checkpw(DEMO_PASSWORD.encode(), first_created["password"].encode())
    assert repository.update_fitness_profile.await_args_list[0].kwargs == {
        "user_id": 1,
        "fitness_goal": "build strength",
        "fitness_level": "intermediate",
        "weight_kg": 78.0,
        "height_cm": 180.0,
        "age": 31,
    }
    assert (
        repository.update_fitness_profile.await_args_list[1].kwargs["fitness_goal"]
        == "improve endurance"
    )
    assert (
        repository.create_user.await_args_list[2].kwargs["email"]
        == "nutrition.admin@example.com"
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_seed_demo_users_does_not_overwrite_existing_users(monkeypatch):
    db = AsyncMock()
    repository = Mock()
    repository.get_by_email = AsyncMock(return_value=Mock(spec=User))
    repository.create_user = AsyncMock()
    repository.update_fitness_profile = AsyncMock()
    monkeypatch.setattr("app.db.demo_seed.UserRepository", lambda _: repository)

    await seed_demo_users(db, settings(seed_demo_users=True))

    assert repository.get_by_email.await_count == len(DEMO_USERS)
    repository.create_user.assert_not_awaited()
    repository.update_fitness_profile.assert_not_awaited()
    db.commit.assert_awaited_once()
