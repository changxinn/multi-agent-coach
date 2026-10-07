"""Recovery API contracts, authenticated access, and transaction failures."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.recovery import get_current_user, recovery_agent_client, router
from app.services.recovery_agent_client import (
    RecoveryAgentUnavailableError,
    RecoveryRecordError,
)


@pytest.fixture
def api_client(monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    db = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: {"id": 1}
    monkeypatch.setattr(recovery_agent_client, "list_records", db.list_records)
    monkeypatch.setattr(recovery_agent_client, "write_record", db.write_record)
    monkeypatch.setattr(recovery_agent_client, "delete_record", db.delete_record)
    with TestClient(app) as client:
        yield client, db, app


PAYLOADS = [
    (
        "sleep-logs",
        {"user_id": 1, "duration_minutes": 480, "quality": 4, "notes": None},
    ),
    (
        "check-ins",
        {"user_id": 1, "energy": 7, "soreness": 3, "stress": 4, "notes": None},
    ),
    (
        "assessments",
        {
            "user_id": 1,
            "status": "green",
            "score": 2,
            "response": {"message": "Rest"},
            "tool_trace": [],
        },
    ),
]


@pytest.mark.parametrize("kind,payload", PAYLOADS)
def test_create_update_list_delete(api_client, kind, payload):
    client, db, _ = api_client
    row = {"id": 12, "created_at": "2026-09-15T00:00:00Z", **payload}
    db.write_record.return_value = row
    for method, url, code in [
        ("post", f"/api/recovery/{kind}", 201),
        ("put", f"/api/recovery/{kind}/12", 200),
    ]:
        response = getattr(client, method)(url, json=payload)
        assert response.status_code == code, response.text
        assert response.json() == row
    assert db.write_record.await_count == 2
    db.write_record.assert_awaited_with(kind, payload, 12)
    db.list_records.return_value = {"items": [row], "total": 1}
    response = client.get(f"/api/recovery/{kind}?user_id=1&page=1&page_size=5")
    assert response.json() == {"items": [row], "total": 1}
    db.list_records.assert_awaited_once_with(kind, 1, 5, 1)
    response = client.delete(f"/api/recovery/{kind}/12")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.parametrize("kind,payload", PAYLOADS)
def test_access_and_validation(api_client, kind, payload):
    client, _, app = api_client
    assert (
        client.post(f"/api/recovery/{kind}", json={**payload, "user_id": 0}).status_code
        == 422
    )
    assert client.get(f"/api/recovery/{kind}?page_size=101").status_code == 422
    del app.dependency_overrides[get_current_user]
    assert client.get(f"/api/recovery/{kind}").status_code in (401, 403)


def test_missing_record_and_foreign_key_failure(api_client):
    client, db, _ = api_client
    kind, payload = PAYLOADS[0]
    db.write_record.side_effect = RecoveryRecordError(404, "Missing")
    db.delete_record.side_effect = RecoveryRecordError(404, "Missing")
    assert client.put(f"/api/recovery/{kind}/999", json=payload).status_code == 404
    assert client.delete(f"/api/recovery/{kind}/999").status_code == 404
    db.write_record.side_effect = RecoveryRecordError(409, "Invalid")
    assert client.post(f"/api/recovery/{kind}", json=payload).status_code == 409
    db.list_records.side_effect = RecoveryAgentUnavailableError("Offline")
    assert client.get(f"/api/recovery/{kind}").status_code == 503


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("sleep-logs", {"user_id": 1, "duration_minutes": 1441, "quality": 6}),
        ("check-ins", {"user_id": 1, "energy": 0, "soreness": 1, "stress": 11}),
        (
            "assessments",
            {
                "user_id": 1,
                "status": "invalid",
                "score": -1,
                "response": [],
                "tool_trace": {},
            },
        ),
    ],
)
def test_recovery_value_ranges(api_client, kind, payload):
    client, db, _ = api_client
    assert client.post(f"/api/recovery/{kind}", json=payload).status_code == 422
    db.write_record.assert_not_awaited()
