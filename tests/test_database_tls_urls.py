"""TLS URL compatibility for bootstrap and direct asyncpg connections."""

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest

from services.database_bootstrap.bootstrap import SERVICES, runtime_database_url
from services.recovery_agent.app.config import Settings
from services.recovery_agent.app.repository import RecoveryRepository


@pytest.mark.parametrize("service", SERVICES, ids=lambda service: service.name)
def test_bootstrap_uses_driver_specific_tls_parameter(service):
    url = runtime_database_url(service, "p@ss/word", "database.example.com")
    parts = urlsplit(url)
    parameter = "sslmode" if service.name == "recovery" else "ssl"

    assert parse_qs(parts.query) == {parameter: ["require"]}
    assert parts.password == "p%40ss%2Fword"
    assert parts.hostname == "database.example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("ssl=require", "sslmode=require"),
        ("sslmode=require", "sslmode=require"),
        (
            "ssl=require&application_name=recovery",
            "sslmode=require&application_name=recovery",
        ),
        ("ssl=require&sslmode=verify-full", "sslmode=verify-full"),
        ("", ""),
    ],
)
async def test_recovery_normalizes_legacy_tls_urls(monkeypatch, query, expected):
    create_pool = AsyncMock()
    monkeypatch.setattr(
        "services.recovery_agent.app.repository.asyncpg.create_pool", create_pool
    )
    base = "postgresql://recovery:p%40ss%2Fword@database.example.com/recovery"
    url = base + (f"?{query}" if query else "")
    repository = RecoveryRepository(Settings(_env_file=None, RECOVERY_DATABASE_URL=url))

    await repository.connect()

    expected_url = base + (f"?{expected}" if expected else "")
    create_pool.assert_awaited_once_with(expected_url, min_size=1, max_size=5)
    await repository.close()
