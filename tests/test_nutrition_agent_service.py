from fastapi.testclient import TestClient

from services.nutrition_agent.app.config import settings
from services.nutrition_agent.app.main import app


def test_health_is_public_and_private_operations_require_token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/v1/nutrition/status").status_code == 405
        missing_token_response = client.post("/v1/nutrition/status", json={})
        wrong_token_response = client.post(
            "/v1/nutrition/status",
            json={},
            headers={"X-Internal-Service-Token": "wrong"},
        )
        ready_response = client.post(
            "/v1/nutrition/status",
            json={},
            headers={"X-Internal-Service-Token": "test-token"},
        )
        assert missing_token_response.status_code == 401
        assert wrong_token_response.status_code == 401
        assert ready_response.json()["status"] == "ready"


def test_private_agent_calculation_matches_phase_one_contract(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    payload = {
        "sex": "male",
        "age": 30,
        "weight_kg": "80",
        "height_cm": "180",
        "activity_level": "moderate",
        "goal": "maintenance",
    }
    with TestClient(app) as client:
        response = client.post(
            "/v1/nutrition/targets/calculate",
            json=payload,
            headers={"X-Internal-Service-Token": "test-token"},
        )

    assert response.status_code == 200
    assert response.json()["calculation_method"] == "mifflin_st_jeor_v1"
