"""Fail-closed guard tests for the chat-history integration database."""

import pytest

from app.db.migrate import chat_history_test_database_url


def test_chat_history_test_database_url_requires_explicit_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CHAT_HISTORY_TEST_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="must be configured"):
        chat_history_test_database_url()


def test_chat_history_test_database_url_rejects_application_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/application"
    monkeypatch.setenv("CHAT_HISTORY_TEST_DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError, match="must not equal"):
        chat_history_test_database_url()


def test_chat_history_test_database_url_rejects_non_chat_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CHAT_HISTORY_TEST_DATABASE_URL", "postgresql://user:password@localhost:5432/systemdb"
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="chat_history_test"):
        chat_history_test_database_url()


def test_chat_history_test_database_url_accepts_disposable_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/chat_history_test"
    monkeypatch.setenv("CHAT_HISTORY_TEST_DATABASE_URL", url)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/application"
    )
    assert chat_history_test_database_url() == url