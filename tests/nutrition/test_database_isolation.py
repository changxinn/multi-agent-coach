"""Fail-closed guard tests for Nutrition integration database configuration."""

from __future__ import annotations

import pytest

from app.db.migrate import test_database_url as isolated_test_database_url


def test_test_database_url_requires_explicit_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NUTRITION_TEST_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="must be configured"):
        isolated_test_database_url()


def test_test_database_url_rejects_application_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/application"
    monkeypatch.setenv("NUTRITION_TEST_DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError, match="must not equal"):
        isolated_test_database_url()


def test_test_database_url_rejects_non_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "NUTRITION_TEST_DATABASE_URL",
        "postgresql://user:password@localhost:5432/systemdb",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="nutrition_test"):
        isolated_test_database_url()


def test_test_database_url_accepts_disposable_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/nutrition_test"
    monkeypatch.setenv("NUTRITION_TEST_DATABASE_URL", url)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/application"
    )
    assert isolated_test_database_url() == url
