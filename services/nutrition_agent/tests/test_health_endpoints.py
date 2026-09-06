"""Health contract tests executed from the Nutrition Agent service root."""

from __future__ import annotations

import httpx
import pytest

import app.main as nutrition_api


class _Connection:
    async def execute(self, query: str) -> None:
        assert query == "SELECT 1"


class _Acquire:
    async def __aenter__(self) -> _Connection:
        return _Connection()

    async def __aexit__(self, *_: object) -> None:
        return None


class _Pool:
    def acquire(self) -> _Acquire:
        return _Acquire()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health/live", "/health"])
async def test_liveness_routes_do_not_contact_dependencies(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    def unexpected(*_: object, **__: object) -> None:
        pytest.fail("liveness must not contact a dependency")

    monkeypatch.setattr(nutrition_api.repository, "validate_schema", unexpected)
    transport = httpx.ASGITransport(app=nutrition_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.asyncio
async def test_missing_profile_uses_structured_not_found_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def get_profile(_: int) -> None:
        return None

    monkeypatch.setattr(nutrition_api.settings, "NUTRITION_INTERNAL_SERVICE_TOKEN", "token")
    monkeypatch.setattr(nutrition_api.repository, "get_profile", get_profile)
    transport = httpx.ASGITransport(app=nutrition_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/nutrition/users/1/profile",
            headers={"X-Internal-Service-Token": "token"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "NUTRITION_PROFILE_NOT_FOUND",
            "message": "The requested nutrition resource was not found.",
        }
    }


@pytest.mark.asyncio
async def test_readiness_sanitizes_configuration_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nutrition_api.settings, "NUTRITION_INTERNAL_SERVICE_TOKEN", "")
    transport = httpx.ASGITransport(app=nutrition_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "failed", "database": "failed", "schema": "failed"},
    }


@pytest.mark.asyncio
async def test_readiness_sanitizes_database_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nutrition_api.settings, "NUTRITION_INTERNAL_SERVICE_TOKEN", "token")
    monkeypatch.setattr(nutrition_api.repository, "pool", None)
    transport = httpx.ASGITransport(app=nutrition_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "ok", "database": "failed", "schema": "failed"},
    }


@pytest.mark.asyncio
async def test_readiness_sanitizes_schema_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def schema_failure() -> None:
        raise RuntimeError("schema details must not appear in the response")

    monkeypatch.setattr(nutrition_api.settings, "NUTRITION_INTERNAL_SERVICE_TOKEN", "token")
    monkeypatch.setattr(nutrition_api.repository, "pool", _Pool())
    monkeypatch.setattr(nutrition_api.repository, "validate_schema", schema_failure)
    transport = httpx.ASGITransport(app=nutrition_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "ok", "database": "ok", "schema": "failed"},
    }


@pytest.mark.asyncio
async def test_readiness_reports_all_healthy_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def validate_schema() -> None:
        return None

    monkeypatch.setattr(nutrition_api.settings, "NUTRITION_INTERNAL_SERVICE_TOKEN", "token")
    monkeypatch.setattr(nutrition_api.repository, "pool", _Pool())
    monkeypatch.setattr(nutrition_api.repository, "validate_schema", validate_schema)
    transport = httpx.ASGITransport(app=nutrition_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "ok", "database": "ok", "schema": "ok"},
    }
