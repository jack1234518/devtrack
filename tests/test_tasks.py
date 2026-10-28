
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
        assert len(listed.json()["items"]) == 1
        assert listed.json()["total"] == 1
        assert listed.json()["page"] == 1

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


def test_task_priority_defaults_to_medium():
    with TestClient(app) as client:
        headers, project_id = create_user_and_project(client)

        response = client.post(
            f"/projects/{project_id}/tasks",
            headers=headers,
            json={"title": "Default priority task"},
        )

        assert response.status_code == 201
        assert response.json()["priority"] == "medium"


def test_task_priority_can_be_set_and_updated():
    with TestClient(app) as client:
        headers, project_id = create_user_and_project(client)
        base = f"/projects/{project_id}/tasks"

        created = client.post(
            base,
            headers=headers,
            json={"title": "Urgent task", "priority": "high"},
        )

        assert created.status_code == 201
        assert created.json()["priority"] == "high"

        task_id = created.json()["id"]

        updated = client.patch(
            f"{base}/{task_id}",
            headers=headers,
            json={"priority": "low"},
        )

        assert updated.status_code == 200
        assert updated.json()["priority"] == "low"

def test_invalid_task_priority_is_rejected():
    with TestClient(app) as client:
        headers, project_id = create_user_and_project(client)

        response = client.post(
            f"/projects/{project_id}/tasks",
            headers=headers,
            json={
                "title": "Invalid priority task",
                "priority": "urgent",
            },
        )

        assert response.status_code == 422


def test_task_filters_search_and_pagination():
    with TestClient(app) as client:
        headers, project_id = create_user_and_project(client)
        base = f"/projects/{project_id}/tasks"

        tasks = [
            {
                "title": "Build FastAPI service",
                "status": "todo",
                "priority": "high",
                "due_date": "2026-11-05",
            },
            {
                "title": "Write database tests",
                "status": "in_progress",
                "priority": "medium",
            },
            {
                "title": "Complete API documentation",
                "status": "completed",
                "priority": "low",
            },
        ]

        for task in tasks:
            response = client.post(
                base,
                headers=headers,
                json=task,
            )
            assert response.status_code == 201

        # Filter by status.
        response = client.get(
            base,
            headers=headers,
            params={"task_status": "in_progress"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "in_progress"

        # Filter by priority.
        response = client.get(
            base,
            headers=headers,
            params={"priority": "high"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["priority"] == "high"

        # Search titles without case sensitivity.
        response = client.get(
            base,
            headers=headers,
            params={"search": "FASTAPI"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Build FastAPI service"

        # Paginate: one result per page.
        response = client.get(
            base,
            headers=headers,
            params={"page": 1, "page_size": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 3
        assert data["total_pages"] == 3
        assert data["has_next"] is True

        response = client.get(
            base,
            headers=headers,
            params={"page": 3, "page_size": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["has_next"] is False
        assert data["has_previous"] is True


def test_overdue_filter_excludes_completed_tasks():
    with TestClient(app) as client:
        headers, project_id = create_user_and_project(client)
        base = f"/projects/{project_id}/tasks"

        overdue_task = client.post(
            base,
            headers=headers,
            json={
                "title": "Overdue unfinished task",
                "due_date": "2020-01-01",
                "status": "todo",
            },
        )
        assert overdue_task.status_code == 201

        completed_task = client.post(
            base,
            headers=headers,
            json={
                "title": "Old but completed task",
                "due_date": "2020-01-01",
                "status": "completed",
            },
        )
        assert completed_task.status_code == 201

        response = client.get(
            base,
            headers=headers,
            params={"overdue": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Overdue unfinished task"
        assert data["items"][0]["is_overdue"] is True


def test_task_pagination_validation():
    with TestClient(app) as client:
        headers, project_id = create_user_and_project(client)
        base = f"/projects/{project_id}/tasks"

        response = client.get(
            base,
            headers=headers,
            params={"page": 0},
        )
        assert response.status_code == 422

        response = client.get(
            base,
            headers=headers,
            params={"page_size": 101},
        )
        assert response.status_code == 422
