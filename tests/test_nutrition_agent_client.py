from datetime import date

import httpx
import pytest

from app.services.nutrition_agent_client import (
    NutritionAgentClient,
    NutritionAgentUnavailableError,
    NutritionMealPlanValidationError,
)


class MealPlanPayload:
    def model_dump(self, *, mode: str):
        assert mode == "json"
        return {
            "target_snapshot_id": 3,
            "start_date": "2026-09-22",
            "end_date": "2026-09-22",
            "planned_meals": [],
        }


@pytest.mark.asyncio
async def test_food_catalogue_client_requests_all_cached_foods(monkeypatch):
    captured = {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, *, headers, json):
            captured.update(url=url, json=json)
            return httpx.Response(
                200,
                json={"items": [{"id": 1, "description": "Chicken breast"}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        "app.services.nutrition_agent_client.httpx.AsyncClient", lambda **_: Client()
    )

    assert await NutritionAgentClient().get_food_catalogue(7) == [
        {"id": 1, "description": "Chicken breast"}
    ]
    assert captured["url"].endswith("/v1/nutrition/foods/catalogue")
    assert captured["json"] == {"user_id": 7}


@pytest.mark.asyncio
async def test_meal_plan_client_forwards_user_payload_and_idempotency(monkeypatch):
    captured = {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, json=json)
            return httpx.Response(
                200,
                json={"id": 41, "version": 1},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        "app.services.nutrition_agent_client.httpx.AsyncClient", lambda **_: Client()
    )

    response = await NutritionAgentClient().create_meal_plan(
        7, MealPlanPayload(), "plan-1"
    )

    assert response == {"id": 41, "version": 1}
    assert captured["url"].endswith("/v1/nutrition/meal-plans/create")
    assert captured["headers"]["Idempotency-Key"] == "plan-1"
    assert captured["json"]["user_id"] == 7
    assert "user_id" not in MealPlanPayload().model_dump(mode="json")


@pytest.mark.asyncio
async def test_meal_plan_generation_client_forwards_scope_and_idempotency(monkeypatch):
    captured = {}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): return False
        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, json=json)
            return httpx.Response(200, json={"id": 42}, request=httpx.Request("POST", url))

    class GenerationPayload:
        def model_dump(self, *, mode: str):
            assert mode == "json"
            return {"start_date": "2026-09-22", "end_date": "2026-09-22", "meal_types": ["breakfast"]}

    monkeypatch.setattr("app.services.nutrition_agent_client.httpx.AsyncClient", lambda **_: Client())
    assert await NutritionAgentClient().generate_meal_plan(7, GenerationPayload(), "generate-1") == {"id": 42}
    assert captured["url"].endswith("/v1/nutrition/meal-plans/generate")
    assert captured["headers"]["Idempotency-Key"] == "generate-1"
    assert captured["json"] == {"user_id": 7, "start_date": "2026-09-22", "end_date": "2026-09-22", "meal_types": ["breakfast"]}


@pytest.mark.asyncio
async def test_meal_plan_read_client_uses_date_scoped_private_routes(monkeypatch):
    requests = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, *, headers, json):
            requests.append((url, json))
            return httpx.Response(
                200,
                json={"meal_plan": {"id": 41}},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        "app.services.nutrition_agent_client.httpx.AsyncClient", lambda **_: Client()
    )
    client = NutritionAgentClient()

    assert await client.get_active_meal_plan(7, date(2026, 9, 22)) == {"id": 41}
    assert await client.get_nutrition_context(7, date(2026, 9, 22)) == {
        "meal_plan": {"id": 41}
    }
    assert requests == [
        (
            "http://localhost:8004/v1/nutrition/meal-plans/active",
            {"user_id": 7, "date": "2026-09-22"},
        ),
        (
            "http://localhost:8004/v1/nutrition/context",
            {"user_id": 7, "date": "2026-09-22"},
        ),
    ]


@pytest.mark.asyncio
async def test_meal_plan_lifecycle_client_forwards_ownership_and_idempotency(
    monkeypatch,
):
    requests = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, *, headers, json):
            requests.append((url, headers, json))
            return httpx.Response(
                200,
                json={"items": []} if url.endswith("/list") else {"id": 41},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        "app.services.nutrition_agent_client.httpx.AsyncClient", lambda **_: Client()
    )
    client = NutritionAgentClient()
    assert await client.list_meal_plans(7) == []
    assert await client.confirm_meal_plan(7, 41, "confirm-1") == {"id": 41}
    assert await client.archive_meal_plan(7, 41, "archive-1") == {"id": 41}
    assert [request[2] for request in requests] == [
        {"user_id": 7},
        {"user_id": 7, "meal_plan_id": 41},
        {"user_id": 7, "meal_plan_id": 41},
    ]
    assert requests[1][1]["Idempotency-Key"] == "confirm-1"
    assert requests[2][1]["Idempotency-Key"] == "archive-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "detail"),
    [
        ("confirm", "Only draft meal plans can be confirmed"),
        ("confirm", "Meal plan is blocked by the user's allergen restrictions"),
        ("archive", "Only draft or active meal plans can be archived"),
    ],
)
async def test_meal_plan_lifecycle_client_preserves_validation_details(
    monkeypatch, operation, detail
):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, *, headers, json):
            return httpx.Response(
                422,
                json={"detail": detail},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        "app.services.nutrition_agent_client.httpx.AsyncClient", lambda **_: Client()
    )
    client = NutritionAgentClient()

    with pytest.raises(NutritionMealPlanValidationError, match=detail):
        if operation == "confirm":
            await client.confirm_meal_plan(7, 41, "confirm-1")
        else:
            await client.archive_meal_plan(7, 41, "archive-1")


@pytest.mark.asyncio
async def test_meal_plan_client_maps_transport_failures_to_unavailable(monkeypatch):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, *_args, **_kwargs):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(
        "app.services.nutrition_agent_client.httpx.AsyncClient", lambda **_: Client()
    )

    with pytest.raises(NutritionAgentUnavailableError, match="temporarily unavailable"):
        await NutritionAgentClient().get_nutrition_context(7, date(2026, 9, 22))
