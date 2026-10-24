
from fastapi.testclient import TestClient

from app.main import app


def test_home():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_project_validation():
    with TestClient(app) as client:
        response = client.post(
            "/projects",
            json={
                "name": "",
                "description": "Invalid project",
                "status": "planned",
            },
        )

    assert response.status_code == 422


def test_invalid_project_status():
    with TestClient(app) as client:
        response = client.post(
            "/projects",
            json={
                "name": "Test project",
                "status": "invalid",
            },
        )

    assert response.status_code == 422
