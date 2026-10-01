from datetime import UTC, date
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user
from app.api.routes.dashboard import (
    get_daily_command_center_service,
    get_daily_training_workout_service,
    router,
)
from app.api.schemas.dashboard import (
    NutritionDashboardSnapshot,
    RecoveryDashboardSnapshot,
)
from app.services.daily_command_center_service import DailyCommandCenterService
from app.services.daily_training_workout_service import DailyTrainingWorkoutService


@pytest.fixture
def dashboard_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    service = AsyncMock()
    service.get.return_value = {
        "generated_at": "2026-09-28T10:00:00Z",
        "dashboard_date": "2026-09-28",
        "training": {
            "status": "unavailable",
            "message": "Your workout log is not yet connected to the daily dashboard.",
            "last_activity_at": None,
        },
        "nutrition": {"status": "unavailable", "trend": []},
        "recovery": {"status": "no_assessment", "trend": []},
        "actions": [],
        "errors": [],
    }
    app.dependency_overrides[get_current_user] = lambda: {"id": 17}
    app.dependency_overrides[get_daily_command_center_service] = lambda: service
    app.dependency_overrides[get_daily_training_workout_service] = lambda: service
    with TestClient(app) as client:
        yield client, service, app


def test_command_center_uses_authenticated_user_id_only(dashboard_client):
    client, service, _ = dashboard_client

    response = client.get("/api/dashboard/daily-command-center?user_id=99")

    assert response.status_code == 200, response.text
    service.get.assert_awaited_once_with(17)
    assert response.json()["dashboard_date"] == "2026-09-28"


def test_command_center_requires_authentication(dashboard_client):
    client, _, app = dashboard_client
    del app.dependency_overrides[get_current_user]

    response = client.get("/api/dashboard/daily-command-center")

    assert response.status_code in (401, 403)


def test_daily_training_workout_uses_authenticated_user_and_refresh_flag(
    dashboard_client,
):
    client, service, _ = dashboard_client
    service.get.return_value = {
        "status": "ready",
        "title": "Today’s personalized workout",
        "workout_text": "Warm-up\nMain work\nCooldown",
        "recovery_status": "green",
        "generated_at": "2026-09-28T10:00:00Z",
        "reused": False,
    }

    response = client.post("/api/dashboard/training/today?refresh=true&user_id=99")

    assert response.status_code == 200, response.text
    service.get.assert_awaited_once_with(17, refresh=True)


def test_dashboard_service_factories_create_services_for_the_request_database():
    db = AsyncMock()

    command_center = get_daily_command_center_service(db)
    training = get_daily_training_workout_service(db)

    assert isinstance(command_center, DailyCommandCenterService)
    assert command_center.db is db
    assert isinstance(training, DailyTrainingWorkoutService)
    assert training.db is db


def test_actions_prioritize_recovery_and_cap_at_three():
    nutrition = NutritionDashboardSnapshot(
        status="available", meal_count=0, remaining_protein_g=50
    )
    recovery = RecoveryDashboardSnapshot(status="escalate")

    actions = DailyCommandCenterService._actions(nutrition, recovery)

    assert [action.id for action in actions] == [
        "recovery-escalation",
        "nutrition-log-meal",
        "training-coach",
    ]
    assert [action.priority for action in actions] == [1, 2, 3]
    assert "session" not in actions[0].description.lower()


def test_unavailable_domains_do_not_create_domain_actions():
    actions = DailyCommandCenterService._actions(
        NutritionDashboardSnapshot(status="unavailable"),
        RecoveryDashboardSnapshot(status="unavailable"),
    )

    assert [action.id for action in actions] == ["training-coach"]


@pytest.mark.asyncio
async def test_service_returns_date_complete_null_gap_trends():
    service = DailyCommandCenterService(AsyncMock(), AsyncMock())
    dashboard_date = date(2026, 9, 28)
    service._nutrition_snapshot = AsyncMock(
        return_value=NutritionDashboardSnapshot(
            status="available",
            trend=[
                {"date": date(2026, 9, 22), "calorie_adherence_pct": 80},
                {"date": date(2026, 9, 23), "calorie_adherence_pct": None},
                *(
                    {"date": day}
                    for day in (
                        date(2026, 9, 24),
                        date(2026, 9, 25),
                        date(2026, 9, 26),
                        date(2026, 9, 27),
                        date(2026, 9, 28),
                    )
                ),
            ],
        )
    )
    service._recovery_snapshot = AsyncMock(
        return_value=RecoveryDashboardSnapshot(
            status="no_assessment",
            trend=[{"date": dashboard_date}],
        )
    )

    result = await service.get(17, dashboard_date)

    assert result.dashboard_date == dashboard_date
    assert len(result.nutrition.trend) == 7
    assert result.nutrition.trend[1].calorie_adherence_pct is None
    assert result.recovery.status == "no_assessment"
    assert result.generated_at.tzinfo == UTC
