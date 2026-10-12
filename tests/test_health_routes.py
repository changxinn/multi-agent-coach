"""Health routes for direct target checks and ALB path-based routing."""

from fastapi.testclient import TestClient

from app.main import app


def test_direct_and_alb_health_routes_return_the_same_healthy_response():
    # Do not enter the context manager: this contract does not need lifespan's
    # database initialization or background session cleanup task.
    client = TestClient(app)
    try:
        direct = client.get("/health")
        through_alb = client.get("/api/health")

        assert direct.status_code == 200
        assert through_alb.status_code == 200
        assert through_alb.json() == direct.json()
        assert direct.json()["status"] == "healthy"
    finally:
        client.close()
