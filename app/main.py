
from contextlib import asynccontextmanager
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.database import create_tables, get_database_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="DevTrack API",
    description="Track software projects, tasks, and deployments.",
    version="0.3.0",
    lifespan=lifespan,
)


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


@app.get("/")
def home():
    return {
        "message": "Welcome to DevTrack API!",
        "status": "running",
        "version": "0.3.0",
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


@app.get("/projects")
def list_projects():
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM projects ORDER BY id"
                )
                return cursor.fetchall()
    except psycopg.Error:
        database_error()


@app.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO projects (name, description, status)
                    VALUES (%s, %s, %s)
                    RETURNING *
                    """,
                    (project.name, project.description, project.status),
                )
                return cursor.fetchone()
    except psycopg.Error:
        database_error()


@app.get("/projects/{project_id}")
def get_project(project_id: int):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM projects WHERE id = %s",
                    (project_id,),
                )
                project = cursor.fetchone()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        return project
    except psycopg.Error:
        database_error()


@app.patch("/projects/{project_id}")
def update_project(project_id: int, updates: ProjectUpdate):
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

    allowed_fields = {"name", "description", "status"}
    if not set(changes).issubset(allowed_fields):
        raise HTTPException(status_code=400, detail="Invalid fields")

    assignments = ", ".join(f"{field} = %s" for field in changes)
    values = list(changes.values())
    values.append(project_id)

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE projects
                    SET {assignments}, updated_at = NOW()
                    WHERE id = %s
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


@app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM projects WHERE id = %s RETURNING id",
                    (project_id,),
                )
                deleted = cursor.fetchone()

        if deleted is None:
            raise HTTPException(status_code=404, detail="Project not found")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except psycopg.Error:
        database_error()
