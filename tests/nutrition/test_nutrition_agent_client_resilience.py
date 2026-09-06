"""Nutrition Agent client retry and circuit-breaker coverage."""

from __future__ import annotations

import httpx
import pytest

from app.services.nutrition_agent_client import (
    NutritionAgentClient,
    NutritionAgentError,
)


@pytest.fixture
async def nutrition_client(monkeypatch: pytest.MonkeyPatch):
    client = NutritionAgentClient()
    monkeypatch.setattr(
        "app.services.nutrition_agent_client.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "NUTRITION_INTERNAL_SERVICE_TOKEN": "internal-token",
                "NUTRITION_AGENT_URL": "http://nutrition-agent",
            },
        )(),
    )
    monkeypatch.setattr("app.services.nutrition_agent_client.random.uniform", lambda *_: 0.0)
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_get_retries_once_after_qualifying_response(
    nutrition_client: NutritionAgentClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503 if attempts == 1 else 200, json={"items": []})

    nutrition_client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.services.nutrition_agent_client.asyncio.sleep", sleep)

    assert await nutrition_client.request("GET", "/v1/nutrition/foods") == {"items": []}
    assert attempts == 2
    assert sleeps == [0.0]
    assert not nutrition_client._failure_times


@pytest.mark.asyncio
async def test_mutation_is_not_retried_after_qualifying_response(
    nutrition_client: NutritionAgentClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    nutrition_client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("app.services.nutrition_agent_client.asyncio.sleep", pytest.fail)

    with pytest.raises(NutritionAgentError):
        await nutrition_client.request("POST", "/v1/nutrition/users/42/meal-logs")

    assert attempts == 1


@pytest.mark.asyncio
async def test_private_validation_detail_is_sanitized_for_the_public_boundary(
    nutrition_client: NutritionAgentClient,
) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "type": "value_error",
                        "loc": ["body", "timezone"],
                        "msg": "Value error, Timezone must be a valid IANA timezone",
                        "input": "Not/A_Timezone",
                    }
                ]
            },
        )

    nutrition_client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(NutritionAgentError) as raised:
        await nutrition_client.request("PUT", "/v1/nutrition/users/42/profile")

    assert raised.value.status_code == 422
    assert raised.value.code == "VALIDATION_ERROR"
    assert raised.value.message == "Value error, Timezone must be a valid IANA timezone"


@pytest.mark.asyncio
async def test_get_retries_once_after_read_timeout(
    nutrition_client: NutritionAgentClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json={"items": []})

    nutrition_client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.services.nutrition_agent_client.asyncio.sleep", sleep)

    assert await nutrition_client.request("GET", "/v1/nutrition/foods") == {"items": []}
    assert attempts == 2
    assert not nutrition_client._failure_times


@pytest.mark.asyncio
async def test_five_qualifying_failures_open_circuit_and_successful_probe_resets_it(
    nutrition_client: NutritionAgentClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = 100.0
    calls = 0

    def monotonic() -> float:
        return now

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503 if calls <= 10 else 200, json={"ok": True})

    nutrition_client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("app.services.nutrition_agent_client.time.monotonic", monotonic)

    async def sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.services.nutrition_agent_client.asyncio.sleep", sleep)

    for _ in range(5):
        with pytest.raises(NutritionAgentError):
            await nutrition_client.request("GET", "/v1/nutrition/foods")

    assert calls == 10
    with pytest.raises(NutritionAgentError):
        await nutrition_client.request("GET", "/v1/nutrition/foods")
    assert calls == 10

    now += 30.0
    assert await nutrition_client.request("GET", "/v1/nutrition/foods") == {"ok": True}
    assert calls == 11
    assert not nutrition_client._failure_times


@pytest.mark.asyncio
async def test_failed_half_open_probe_reopens_circuit(
    nutrition_client: NutritionAgentClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = 100.0
    calls = 0

    def monotonic() -> float:
        return now

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    nutrition_client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("app.services.nutrition_agent_client.time.monotonic", monotonic)

    async def sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.services.nutrition_agent_client.asyncio.sleep", sleep)

    for _ in range(5):
        with pytest.raises(NutritionAgentError):
            await nutrition_client.request("GET", "/v1/nutrition/foods")

    assert calls == 10
    now += 30.0

    with pytest.raises(NutritionAgentError):
        await nutrition_client.request("GET", "/v1/nutrition/foods")

    assert calls == 12
    with pytest.raises(NutritionAgentError):
        await nutrition_client.request("GET", "/v1/nutrition/foods")
    assert calls == 12