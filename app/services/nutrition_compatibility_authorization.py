"""Explicit allowlist authorization for Nutrition compatibility review."""

from fastapi import HTTPException, status

from app.config import Settings


def is_nutrition_compatibility_admin(email: str, settings: Settings) -> bool:
    """Return whether an email matches the configured reviewer, failing closed."""
    configured_email = settings.NUTRITION_COMPATIBILITY_ADMIN_EMAIL.strip().casefold()
    return bool(configured_email) and email.strip().casefold() == configured_email


def require_nutrition_compatibility_admin(email: str, settings: Settings) -> None:
    """Raise 403 unless the authenticated email is the configured reviewer."""
    if not is_nutrition_compatibility_admin(email, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compatibility reviewer access is required",
        )
