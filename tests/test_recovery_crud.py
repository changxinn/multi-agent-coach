"""Recovery API contracts, access control, and transaction failures (no live DB required)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.routes.recovery import get_current_user, get_db, router


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    db = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "role": "admin"}
    app.dependency_overrides[get_db] = lambda: db
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
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    db.execute.return_value = result
    for method, url, code in [
        ("post", f"/api/recovery/{kind}", 201),
        ("put", f"/api/recovery/{kind}/12", 200),
    ]:
        response = getattr(client, method)(url, json=payload)
        assert response.status_code == code, response.text
        assert response.json() == row
    assert db.commit.await_count == 2
    db.scalar.return_value = 1
    result.mappings.return_value = [row]
    response = client.get(f"/api/recovery/{kind}?user_id=1&page=1&page_size=5")
    assert response.json() == {"items": [row], "total": 1}
    statement = db.execute.call_args.args[0]
    assert statement.compile().params["user_id_1"] == 1
    result.scalar_one_or_none.return_value = 12
    response = client.delete(f"/api/recovery/{kind}/12")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.parametrize("kind,payload", PAYLOADS)
def test_access_and_validation(api_client, kind, payload):
    client, db, app = api_client
    assert (
        client.post(f"/api/recovery/{kind}", json={**payload, "user_id": 0}).status_code
        == 422
    )
    assert client.get(f"/api/recovery/{kind}?page_size=101").status_code == 422
    app.dependency_overrides[get_current_user] = lambda: {"id": 2, "role": "user"}
    for method, suffix in [("get", ""), ("post", ""), ("put", "/1"), ("delete", "/1")]:
        assert (
            client.request(
                method, f"/api/recovery/{kind}{suffix}", json=payload
            ).status_code
            == 403
        )
    db.execute.assert_not_awaited()
    del app.dependency_overrides[get_current_user]
    assert client.get(f"/api/recovery/{kind}").status_code in (401, 403)


def test_missing_record_and_foreign_key_failure(api_client):
    client, db, _ = api_client
    kind, payload = PAYLOADS[0]
    result = MagicMock()
    result.mappings.return_value.first.return_value = None
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    assert client.put(f"/api/recovery/{kind}/999", json=payload).status_code == 404
    assert client.delete(f"/api/recovery/{kind}/999").status_code == 404
    db.execute.side_effect = IntegrityError("insert", {}, Exception("foreign key"))
    assert client.post(f"/api/recovery/{kind}", json=payload).status_code == 409
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


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
    db.execute.assert_not_awaited()
