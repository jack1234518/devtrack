
import re
from contextlib import asynccontextmanager
from typing import Literal

import jwt
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field

from app.database import create_tables, get_database_connection
from app.security import (
    ACCESS_TOKEN_MINUTES,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="DevTrack API",
    description="Track software projects, tasks, and deployments.",
    version="0.4.0",
    lifespan=lifespan,
)

bearer_scheme = HTTPBearer(auto_error=False)


class UserRegister(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    status: Literal["planned", "in_progress", "completed"] = "planned"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    status: Literal["planned", "in_progress", "completed"] | None = None


def database_error():
    raise HTTPException(
        status_code=503,
        detail="Database operation failed. Check that PostgreSQL is running.",
    )


def normalize_email(email: str) -> str:
    """Normalize and perform basic validation of an email address."""
    normalized = email.strip().lower()

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(
            status_code=422,
            detail="Enter a valid email address.",
        )

    return normalized


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Authenticate a request and return the corresponding database user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, email FROM users WHERE id = %s",
                    (user_id,),
                )
                user = cursor.fetchone()

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="User account no longer exists.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    except psycopg.Error:
        database_error()


@app.get("/")
def home():
    return {
        "message": "Welcome to DevTrack API!",
        "status": "running",
        "version": "0.4.0",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/db-check")
def database_check():
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database() AS database_name"
                )
                result = cursor.fetchone()

        return {
            "status": "connected",
            "database": result["database_name"],
        }
    except psycopg.Error:
        database_error()


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegister):
    email = normalize_email(user.email)
    hashed_password = hash_password(user.password)

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (email, password_hash)
                    VALUES (%s, %s)
                    RETURNING id, email, created_at
                    """,
                    (email, hashed_password),
                )
                return cursor.fetchone()

    except UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )
    except psycopg.Error:
        database_error()


@app.post("/auth/login")
def login_user(user: UserLogin):
    email = normalize_email(user.email)

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, email, password_hash
                    FROM users
                    WHERE email = %s
                    """,
                    (email,),
                )
                database_user = cursor.fetchone()

    except psycopg.Error:
        database_error()

    if (
        database_user is None
        or not verify_password(user.password, database_user["password_hash"])
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(database_user["id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


@app.get("/projects")
def list_projects(current_user: dict = Depends(get_current_user)):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM projects
                    WHERE user_id = %s
                    ORDER BY id
                    """,
                    (current_user["id"],),
                )
                return cursor.fetchall()
    except psycopg.Error:
        database_error()


@app.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(
    project: ProjectCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO projects
                        (name, description, status, user_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        project.name,
                        project.description,
                        project.status,
                        current_user["id"],
                    ),
                )
                return cursor.fetchone()
    except psycopg.Error:
        database_error()


@app.get("/projects/{project_id}")
def get_project(
    project_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM projects
                    WHERE id = %s AND user_id = %s
                    """,
                    (project_id, current_user["id"]),
                )
                project = cursor.fetchone()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        return project
    except psycopg.Error:
        database_error()


@app.patch("/projects/{project_id}")
def update_project(
    project_id: int,
    updates: ProjectUpdate,
    current_user: dict = Depends(get_current_user),
):
    changes = updates.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update.",
        )

    if any(value is None for value in changes.values()):
        raise HTTPException(
            status_code=422,
            detail="Fields cannot be set to null. Provide valid values.",
        )

    assignments = ", ".join(f"{field} = %s" for field in changes)
    values = list(changes.values())
    values.extend([project_id, current_user["id"]])

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE projects
                    SET {assignments}, updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                    RETURNING *
                    """,
                    values,
                )
                project = cursor.fetchone()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        return project
    except psycopg.Error:
        database_error()


@app.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(
    project_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM projects
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                    """,
                    (project_id, current_user["id"]),
                )
                deleted = cursor.fetchone()

        if deleted is None:
            raise HTTPException(status_code=404, detail="Project not found")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except psycopg.Error:
        database_error()
