"""Named Nutrition Agent client operation coverage."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.nutrition_agent_client import NutritionAgentClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "args", "expected", "result"),
    [
        ("get_profile", (42,), ("GET", 42, "/profile", {}), {"ok": True}),
        ("upsert_profile", (42, {"timezone": "UTC"}), ("PUT", 42, "/profile", {"json": {"timezone": "UTC"}}), {"ok": True}),
        ("delete_profile", (42,), ("DELETE", 42, "/profile", {}), None),
        ("create_meal_log", (42, {"meal_type": "lunch"}), ("POST", 42, "/meal-logs", {"json": {"meal_type": "lunch"}}), {"ok": True}),
        ("list_meal_logs", (42, {"limit": 20, "offset": 0, "start_date": "2026-09-01", "end_date": "2026-09-03", "timezone": "America/New_York"}), ("GET", 42, "/meal-logs", {"params": {"limit": 20, "offset": 0, "start_date": "2026-09-01", "end_date": "2026-09-03", "timezone": "America/New_York"}}), {"ok": True}),
        ("get_meal_log", (42, 9), ("GET", 42, "/meal-logs/9", {}), {"ok": True}),
        ("replace_meal_log", (42, 9, {"meal_type": "dinner"}), ("PUT", 42, "/meal-logs/9", {"json": {"meal_type": "dinner"}}), {"ok": True}),
        ("delete_meal_log", (42, 9), ("DELETE", 42, "/meal-logs/9", {}), None),
        ("calculate_targets", (42, {"inputs": {}}), ("POST", 42, "/targets/calculate", {"json": {"inputs": {}}}), {"ok": True}),
        ("save_target", (42, {"inputs": {}}), ("POST", 42, "/targets", {"json": {"inputs": {}}}), {"ok": True}),
        ("get_current_target", (42, "2026-09-03"), ("GET", 42, "/targets/current", {"params": {"date": "2026-09-03"}}), {"ok": True}),
        ("get_history", (42, {"timezone": "UTC"}), ("GET", 42, "/history", {"params": {"timezone": "UTC"}}), {"ok": True}),
        ("get_assessment_history", (42, {"limit": 20}), ("GET", 42, "/assessment-history", {"params": {"limit": 20}}), {"ok": True}),
        ("generate_meal_plan", (42, {"days": 1}), ("POST", 42, "/meal-plans", {"json": {"days": 1}}), {"ok": True}),
    ],
)
async def test_named_operation_delegates_to_its_private_contract_route(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    args: tuple[Any, ...],
    expected: tuple[str, int, str, dict[str, Any]],
    result: dict[str, bool] | None,
) -> None:
    client = NutritionAgentClient()
    captured: dict[str, Any] = {}

    async def request_for_user(
        method: str, user_id: int, path: str, **kwargs: Any
    ) -> dict[str, bool]:
        captured.update(method=method, user_id=user_id, path=path, **kwargs)
        return {"ok": True}

    monkeypatch.setattr(client, "request_for_user", request_for_user)

    assert await getattr(client, operation)(*args) == result
    method, user_id, path, kwargs = expected
    assert captured == {"method": method, "user_id": user_id, "path": path, **kwargs}