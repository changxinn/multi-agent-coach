import pytest
from fastapi.testclient import TestClient

from services.head_coach.app.config import settings as head_coach_settings
from services.head_coach.app.main import app as head_coach_app
from services.summarizer.app.config import settings as summarizer_settings
from services.summarizer.app.main import app as summarizer_app


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("USE_HEAD_COACH_SERVICE", raising=False)
    monkeypatch.delenv("USE_SUMMARIZER_SERVICE", raising=False)


def test_head_coach_route_requires_token():
    client = TestClient(head_coach_app)
    response = client.post("/v1/head-coach/route", json={"messages": []})
    assert response.status_code == 401


def test_head_coach_routes_training_request(monkeypatch):
    monkeypatch.setattr(head_coach_settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    client = TestClient(head_coach_app)
    response = client.post(
        "/v1/head-coach/route",
        headers={"X-Internal-Service-Token": "test-token"},
        json={
            "volley_msg_left": 1,
            "user_profile": {"goal": "Hyrox", "fitness_level": "beginner"},
            "messages": [
                {"role": "user", "content": "You: Plan a gym workout with squats"}
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_agent"] == "training_planner"
    assert body["selected_agent"] == "training_planner"
    assert body["volley_msg_left"] == 0


def test_head_coach_escalates_medical_risk(monkeypatch):
    monkeypatch.setattr(head_coach_settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    client = TestClient(head_coach_app)
    response = client.post(
        "/v1/head-coach/route",
        headers={"X-Internal-Service-Token": "test-token"},
        json={
            "volley_msg_left": 1,
            "messages": [
                {"role": "user", "content": "You: I have chest pain after training"}
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_agent"] == "human"
    assert "medical_escalation" in body["safety_flags"]
    assert body["messages"]


def test_summarizer_endpoint(monkeypatch):
    monkeypatch.setattr(summarizer_settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    client = TestClient(summarizer_app)
    response = client.post(
        "/v1/summarizer/summarize",
        headers={"X-Internal-Service-Token": "test-token"},
        json={
            "user_profile": {"goal": "Hyrox", "fitness_level": "beginner"},
            "messages": [{"role": "user", "content": "You: Plan a workout"}],
            "progress_text": "Workouts logged: 0",
        },
    )
    assert response.status_code == 200
    assert "SESSION SUMMARY" in response.json()["summary"]


def test_summarizer_daily_endpoint(monkeypatch):
    monkeypatch.setattr(summarizer_settings, "INTERNAL_SERVICE_TOKEN", "test-token")
    client = TestClient(summarizer_app)
    response = client.post(
        "/v1/summarizer/summarize",
        headers={"X-Internal-Service-Token": "test-token"},
        json={
            "user_profile": {"goal": "Hyrox", "fitness_level": "beginner"},
            "messages": [],
            "progress_text": "Workouts logged: 0",
            "summary_kind": "daily",
        },
    )
    assert response.status_code == 200
    assert "Your day at a glance" not in response.json()["summary"]
    assert "bestie" in response.json()["summary"].lower()
