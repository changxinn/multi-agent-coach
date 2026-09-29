import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.nutrition_compatibility_authorization import (
    is_nutrition_compatibility_admin,
    require_nutrition_compatibility_admin,
)


def settings(admin_email: str) -> Settings:
    return Settings(
        JWT_SECRET_KEY="test-secret",
        DATABASE_URL="postgresql+asyncpg://user:password@localhost/test",
        OPENAI_API_KEY="",
        NUTRITION_COMPATIBILITY_ADMIN_EMAIL=admin_email,
    )


def test_compatibility_admin_allowlist_is_case_insensitive_and_fails_closed():
    assert is_nutrition_compatibility_admin(
        " Nutrition.Admin@Example.com ", settings("nutrition.admin@example.com")
    )
    assert not is_nutrition_compatibility_admin(
        "member@example.com", settings("nutrition.admin@example.com")
    )
    assert not is_nutrition_compatibility_admin(
        "nutrition.admin@example.com", settings("")
    )


def test_require_compatibility_admin_rejects_unconfigured_or_nonmatching_users():
    require_nutrition_compatibility_admin(
        "nutrition.admin@example.com", settings("nutrition.admin@example.com")
    )

    with pytest.raises(HTTPException) as error:
        require_nutrition_compatibility_admin("member@example.com", settings(""))

    assert error.value.status_code == 403
    assert error.value.detail == "Compatibility reviewer access is required"
