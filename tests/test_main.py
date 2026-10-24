
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def new_email():
    return f"{uuid4().hex}@example.com"


def register_and_login(client):
    email = new_email()
    password = "Correct-Horse-123!"

    registration = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert registration.status_code == 201

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200

    token_data = login.json()
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == 1800

    return email, {
        "Authorization": f"Bearer {token_data['access_token']}"
    }


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


def test_register_and_login():
    with TestClient(app) as client:
        email, headers = register_and_login(client)

        response = client.get("/projects", headers=headers)

    assert email.endswith("@example.com")
    assert response.status_code == 200
    assert response.json() == []


def test_registration_normalizes_email():
    with TestClient(app) as client:
        email = new_email()

        response = client.post(
            "/auth/register",
            json={"email": f"  {email.upper()}  ", "password": "Strong-Password-123"},
        )

    assert response.status_code == 201
    assert response.json()["email"] == email


def test_duplicate_registration_is_rejected():
    with TestClient(app) as client:
        email = new_email()
        payload = {"email": email, "password": "Strong-Password-123"}

        first = client.post("/auth/register", json=payload)
        second = client.post("/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_short_password_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": new_email(), "password": "short"},
        )

    assert response.status_code == 422


def test_invalid_email_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "Strong-Password-123"},
        )

    assert response.status_code == 422


def test_wrong_password_is_rejected():
    with TestClient(app) as client:
        email = new_email()

        client.post(
            "/auth/register",
            json={"email": email, "password": "Correct-Password-123"},
        )
        response = client.post(
            "/auth/login",
            json={"email": email, "password": "Wrong-Password-123"},
        )

    assert response.status_code == 401


def test_projects_require_authentication():
    with TestClient(app) as client:
        response = client.get("/projects")

    assert response.status_code == 401


def test_invalid_token_is_rejected():
    with TestClient(app) as client:
        response = client.get(
            "/projects",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401


def test_project_crud_and_owner_isolation():
    with TestClient(app) as client:
        _, owner_headers = register_and_login(client)
        _, other_headers = register_and_login(client)

        created = client.post(
            "/projects",
            headers=owner_headers,
            json={
                "name": "DevTrack Authentication",
                "description": "Add secure user login",
                "status": "planned",
            },
        )

        assert created.status_code == 201
        project = created.json()
        project_id = project["id"]
        assert project["name"] == "DevTrack Authentication"

        listed = client.get("/projects", headers=owner_headers)
        assert listed.status_code == 200
        assert any(item["id"] == project_id for item in listed.json())

        retrieved = client.get(
            f"/projects/{project_id}",
            headers=owner_headers,
        )
        assert retrieved.status_code == 200

        updated = client.patch(
            f"/projects/{project_id}",
            headers=owner_headers,
            json={"status": "in_progress"},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "in_progress"

        other_get = client.get(
            f"/projects/{project_id}",
            headers=other_headers,
        )
        other_update = client.patch(
            f"/projects/{project_id}",
            headers=other_headers,
            json={"name": "Unauthorized change"},
        )
        other_delete = client.delete(
            f"/projects/{project_id}",
            headers=other_headers,
        )

        assert other_get.status_code == 404
        assert other_update.status_code == 404
        assert other_delete.status_code == 404

        deleted = client.delete(
            f"/projects/{project_id}",
            headers=owner_headers,
        )
        assert deleted.status_code == 204

        missing = client.get(
            f"/projects/{project_id}",
            headers=owner_headers,
        )
        assert missing.status_code == 404


def test_create_project_validation():
    with TestClient(app) as client:
        _, headers = register_and_login(client)

        response = client.post(
            "/projects",
            headers=headers,
            json={
                "name": "",
                "description": "Invalid project",
                "status": "planned",
            },
        )

    assert response.status_code == 422


def test_invalid_project_status():
    with TestClient(app) as client:
        _, headers = register_and_login(client)

        response = client.post(
            "/projects",
            headers=headers,
            json={
                "name": "Test project",
                "status": "invalid",
            },
        )

    assert response.status_code == 422
