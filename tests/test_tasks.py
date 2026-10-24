
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def create_user_and_project(client):
    email = f"{uuid4().hex}@example.com"
    password = "Strong-Password-123"

    response = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200

    headers = {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }

    response = client.post(
        "/projects",
        headers=headers,
        json={"name": "Task Test Project"},
    )
    assert response.status_code == 201

    return headers, response.json()["id"]


def test_task_crud_and_progress():
    with TestClient(app) as client:
        headers, project_id = create_user_and_project(client)
        base = f"/projects/{project_id}/tasks"

        created = client.post(
            base,
            headers=headers,
            json={"title": "Build API", "status": "todo"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        listed = client.get(base, headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        updated = client.patch(
            f"{base}/{task_id}",
            headers=headers,
            json={"status": "completed"},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "completed"

        progress = client.get(
            f"/projects/{project_id}/progress",
            headers=headers,
        )
        assert progress.status_code == 200
        assert progress.json()["total_tasks"] == 1
        assert progress.json()["completed_tasks"] == 1
        assert progress.json()["completion_percentage"] == 100.0

        deleted = client.delete(
            f"{base}/{task_id}",
            headers=headers,
        )
        assert deleted.status_code == 204


def test_task_requires_authentication():
    with TestClient(app) as client:
        response = client.get("/projects/1/tasks")

    assert response.status_code == 401


def test_invalid_task_status_rejected():
    with TestClient(app) as client:
        headers, project_id = create_user_and_project(client)

        response = client.post(
            f"/projects/{project_id}/tasks",
            headers=headers,
            json={"title": "Invalid task", "status": "invalid"},
        )

    assert response.status_code == 422


def test_other_user_cannot_access_project_tasks():
    with TestClient(app) as client:
        owner_headers, project_id = create_user_and_project(client)
        other_headers, _ = create_user_and_project(client)

        response = client.post(
            f"/projects/{project_id}/tasks",
            headers=owner_headers,
            json={"title": "Private task"},
        )
        assert response.status_code == 201

        response = client.get(
            f"/projects/{project_id}/tasks",
            headers=other_headers,
        )

    assert response.status_code == 404
