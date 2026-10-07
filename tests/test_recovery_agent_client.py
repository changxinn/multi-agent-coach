from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from app.services import recovery_agent_client as module


@pytest.fixture
def remote(monkeypatch):
    requests = []
    state = {"status": 200, "body": {"items": [], "total": 0}}

    def handler(request):
        requests.append(request)
        return httpx.Response(state["status"], json=state["body"])

    original = httpx.AsyncClient
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            INTERNAL_SERVICE_TOKEN="internal-test",
            RECOVERY_AGENT_URL="http://recovery-agent:8001",
        ),
    )
    return module.RecoveryAgentClient(), requests, state


@pytest.mark.asyncio
async def test_client_routes_records_and_sends_private_token(remote):
    client, requests, state = remote
    assert await client.list_records("sleep-logs", 2, 5, 42) == {
        "items": [],
        "total": 0,
    }
    assert requests[0].url.path == "/v1/recovery/records/sleep-logs"
    assert requests[0].url.params["user_id"] == "42"
    assert requests[0].headers["X-Internal-Service-Token"] == "internal-test"
    state["status"] = 204
    await client.delete_record("sleep-logs", 3)
    assert requests[-1].method == "DELETE"
    with pytest.raises(ValueError, match="Unknown"):
        await client.list_records("users", 1, 10)
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,error",
    [
        (404, module.RecoveryRecordError),
        (409, module.RecoveryRecordError),
        (401, module.RecoveryAgentUnavailableError),
        (500, module.RecoveryAgentUnavailableError),
    ],
)
async def test_client_translates_service_errors(remote, status, error):
    client, _, state = remote
    state["status"] = status
    with pytest.raises(error):
        await client.list_records("sleep-logs", 1, 10)


@pytest.mark.asyncio
async def test_dashboard_decodes_dates_for_existing_trend_builder(remote):
    client, requests, state = remote
    row = {"created_at": "2026-10-06T01:00:00Z", "status": "green", "score": 0}
    state["body"] = {
        "latest_assessment": dict(row),
        "latest_sleep": None,
        "latest_checkin": None,
        "sleep_trend": [],
        "assessment_trend": [dict(row)],
    }
    data = await client.dashboard_data(42, date(2026, 9, 30), date(2026, 10, 6))
    assert data["latest_assessment"]["created_at"].date() == date(2026, 10, 6)
    assert data["assessment_trend"][0]["created_at"].tzinfo is not None
    assert requests[0].url.params["start_date"] == "2026-09-30"
