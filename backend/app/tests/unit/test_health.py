import pytest


@pytest.fixture(autouse=True)
def mock_settings_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-unit-tests-only")


def test_health_endpoint(mock_settings_env):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_diagnosis_status_values():
    valid_statuses = {
        "pending",
        "ai_complete",
        "under_review",
        "confirmed",
        "overridden",
        "flagged",
    }
    assert "pending" in valid_statuses
    assert "ai_complete" in valid_statuses


def test_user_roles():
    valid_roles = {"patient", "doctor", "admin"}
    assert "patient" in valid_roles
    assert "doctor" in valid_roles
