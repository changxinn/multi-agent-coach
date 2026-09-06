"""Contract coverage for main API health routes."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

import app.main as main_api


class _AsyncContext:
    async def __aenter__(self) -> object:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, _: object) -> None:
        return None


class _MainEngine:
    def begin(self) -> _AsyncContext:
        return _AsyncContext()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health/live", "/health"])
async def test_main_liveness_routes_do_not_contact_dependencies(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    def unexpected(*_: object, **__: object) -> None:
        pytest.fail("liveness must not contact a dependency")

    monkeypatch.setattr(main_api, "engine", SimpleNamespace(begin=unexpected))
    transport = httpx.ASGITransport(app=main_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.asyncio
async def test_main_readiness_sanitizes_configuration_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_api.settings, "NUTRITION_INTERNAL_SERVICE_TOKEN", "")
    transport = httpx.ASGITransport(app=main_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "failed", "database": "failed", "schema": "failed"},
    }


@pytest.mark.asyncio
async def test_main_readiness_reports_all_healthy_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def compatible_schema() -> SimpleNamespace:
        return SimpleNamespace(compatible=True)

    monkeypatch.setattr(main_api, "_configuration_ready", lambda: True)
    monkeypatch.setattr(main_api, "engine", _MainEngine())
    monkeypatch.setattr("app.db.migrate.validate_compatible_schema", compatible_schema)
    transport = httpx.ASGITransport(app=main_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "ok", "database": "ok", "schema": "ok"},
    }


@pytest.mark.asyncio
async def test_main_readiness_sanitizes_database_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def database_failure() -> _AsyncContext:
        raise RuntimeError("database password must not appear in the response")

    monkeypatch.setattr(main_api, "_configuration_ready", lambda: True)
    monkeypatch.setattr(main_api, "engine", SimpleNamespace(begin=database_failure))
    transport = httpx.ASGITransport(app=main_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "ok", "database": "failed", "schema": "failed"},
    }


@pytest.mark.asyncio
async def test_main_readiness_sanitizes_schema_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def incompatible_schema() -> SimpleNamespace:
        return SimpleNamespace(compatible=False)

    monkeypatch.setattr(main_api, "_configuration_ready", lambda: True)
    monkeypatch.setattr(main_api, "engine", _MainEngine())
    monkeypatch.setattr("app.db.migrate.validate_compatible_schema", incompatible_schema)
    transport = httpx.ASGITransport(app=main_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "ok", "database": "ok", "schema": "failed"},
    }