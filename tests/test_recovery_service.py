"""Private Recovery service contracts, authentication and database isolation."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.recovery_agent.app import main
from services.recovery_agent.app.assessment import RecoveryHistory
from services.recovery_agent.app.config import Settings


@pytest.fixture
def client(monkeypatch):
    repository = AsyncMock()
    monkeypatch.setattr(main, "repository", repository)
    monkeypatch.setattr(main.settings, "INTERNAL_SERVICE_TOKEN", "test-recovery-token")
    with TestClient(main.app) as client:
        yield client, repository


def test_recovery_settings_do_not_inherit_main_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://main:main@main-db/systemdb")
    monkeypatch.setenv("DATABASE_SCHEMA", "systemdb")
    monkeypatch.delenv("RECOVERY_DATABASE_URL", raising=False)
    monkeypatch.delenv("RECOVERY_DATABASE_SCHEMA", raising=False)
    settings = Settings(_env_file=None)
    assert settings.DATABASE_URL == ""
    assert settings.DATABASE_SCHEMA == "recovery"
    monkeypatch.setenv(
        "RECOVERY_DATABASE_URL", "postgresql://recovery@recovery-db/recoverydb"
    )
    assert "recoverydb" in Settings(_env_file=None).DATABASE_URL


@pytest.mark.parametrize(
    "resource,payload",
    [
        (
            "sleep-logs",
            {"user_id": 42, "duration_minutes": 480, "quality": 4, "notes": None},
        ),
        (
            "check-ins",
            {"user_id": 42, "energy": 8, "soreness": 2, "stress": 3, "notes": None},
        ),
        (
            "assessments",
            {
                "user_id": 42,
                "status": "green",
                "score": 0,
                "response": {},
                "tool_trace": [],
            },
        ),
    ],
)
def test_internal_crud_requires_token_and_preserves_contract(client, resource, payload):
    client, repo = client
    url = f"/v1/recovery/records/{resource}"
    assert client.get(url).status_code == 401
    repo.list_records.assert_not_awaited()
    headers = {"X-Internal-Service-Token": "test-recovery-token"}
    repo.write_record.return_value = {"id": 3, **payload}
    repo.list_records.return_value = {"items": [], "total": 0}
    repo.delete_record.return_value = True
    assert client.post(url, json=payload, headers=headers).status_code == 201
    assert client.put(url + "/3", json=payload, headers=headers).json()["id"] == 3
    assert client.get(url + "?user_id=42", headers=headers).json() == {
        "items": [],
        "total": 0,
    }
    repo.list_records.assert_awaited_once_with(resource, 1, 10, 42)
    assert client.delete(url + "/3", headers=headers).status_code == 204
    repo.write_record.return_value = None
    assert client.put(url + "/3", json=payload, headers=headers).status_code == 404
    repo.delete_record.return_value = False
    assert client.delete(url + "/3", headers=headers).status_code == 404


def test_dashboard_is_private_and_validates_range(client):
    client, repo = client
    path = "/v1/recovery/dashboard/42?start_date=2026-10-01&end_date=2026-10-06"
    assert client.get(path).status_code == 401
    headers = {"X-Internal-Service-Token": "test-recovery-token"}
    repo.dashboard_data.return_value = {"latest_assessment": None}
    assert client.get(path, headers=headers).status_code == 200
    assert (
        client.get(
            path.replace("2026-10-06", "2026-12-06"), headers=headers
        ).status_code
        == 422
    )
    assert (
        client.get(
            path.replace("dashboard/42", "dashboard/0"), headers=headers
        ).status_code
        == 422
    )


@pytest.mark.asyncio
async def test_repository_requires_its_own_database_configuration():
    from services.recovery_agent.app.repository import RecoveryRepository

    with pytest.raises(RuntimeError, match="RECOVERY_DATABASE_URL"):
        await RecoveryRepository(
            Settings(_env_file=None, RECOVERY_DATABASE_URL="")
        ).connect()


def test_chat_saves_reported_sleep_and_checkin(client):
    client, repo = client
    repo.get_history.return_value = RecoveryHistory()
    response = client.post(
        "/v1/recovery/evaluate",
        headers={"X-Internal-Service-Token": "test-recovery-token"},
        json={
            "user_id": 42,
            "message": "I slept 7.5 hours, sleep quality 4/5. "
            "Energy 7/10, soreness 3/10, stress 4/10.",
        },
    )
    assert response.status_code == 200
    assert (
        "Saved to Recovery Table: sleep log and recovery check-in."
        in response.json()["message"]
    )
    sleep = repo.create_sleep_log.await_args.args[0]
    assert (sleep.user_id, sleep.duration_minutes, sleep.quality) == (42, 450, 4)
    checkin = repo.create_checkin.await_args.args[0]
    assert (checkin.user_id, checkin.energy, checkin.soreness, checkin.stress) == (
        42,
        7,
        3,
        4,
    )
    repo.save_assessment.assert_awaited_once()


def test_chat_does_not_invent_missing_values_or_log_a_plan(client):
    client, repo = client
    repo.get_history.return_value = RecoveryHistory()
    headers = {"X-Internal-Service-Token": "test-recovery-token"}
    response = client.post(
        "/v1/recovery/evaluate",
        headers=headers,
        json={"user_id": 42, "message": "I slept 8 hours. Energy 7/10."},
    )
    assert response.status_code == 200
    assert "send duration and quality" in response.json()["message"]
    assert "send energy, soreness and stress" in response.json()["message"]
    repo.create_sleep_log.assert_not_awaited()
    repo.create_checkin.assert_not_awaited()

    repo.reset_mock()
    repo.get_history.return_value = RecoveryHistory()
    response = client.post(
        "/v1/recovery/evaluate",
        headers=headers,
        json={
            "user_id": 42,
            "message": "I want to sleep 8 hours. Make a recovery plan.",
        },
    )
    assert response.status_code == 200
    assert "Saved to Recovery Table" not in response.json()["message"]
    repo.create_sleep_log.assert_not_awaited()


def test_chat_accepts_minutes_and_rejects_invalid_scales(client):
    client, repo = client
    repo.get_history.return_value = RecoveryHistory()
    response = client.post(
        "/v1/recovery/evaluate",
        headers={"X-Internal-Service-Token": "test-recovery-token"},
        json={
            "user_id": 42,
            "message": "Log sleep: 480 minutes, quality 4/5, stress 11/10",
        },
    )
    assert response.status_code == 200
    sleep = repo.create_sleep_log.await_args.args[0]
    assert (sleep.duration_minutes, sleep.quality) == (480, 4)
    repo.create_checkin.assert_not_awaited()
