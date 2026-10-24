
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.database import get_database_connection
from app.main import get_current_user


router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["Tasks"])


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: Literal["todo", "in_progress", "completed"] = "todo"


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: Literal["todo", "in_progress", "completed"] | None = None


def ensure_project_owner(cursor, project_id: int, user_id: int):
    cursor.execute(
        "SELECT id FROM projects WHERE id = %s AND user_id = %s",
        (project_id, user_id),
    )

    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int,
    task: TaskCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(cursor, project_id, current_user["id"])

                cursor.execute(
                    """
                    INSERT INTO tasks (project_id, title, description, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (project_id, task.title, task.description, task.status),
                )
                return cursor.fetchone()
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )


@router.get("")
def list_tasks(
    project_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(cursor, project_id, current_user["id"])

                cursor.execute(
                    "SELECT * FROM tasks WHERE project_id = %s ORDER BY id",
                    (project_id,),
                )
                return cursor.fetchall()
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )


@router.get("/{task_id}")
def get_task(
    project_id: int,
    task_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(cursor, project_id, current_user["id"])

                cursor.execute(
                    """
                    SELECT * FROM tasks
                    WHERE id = %s AND project_id = %s
                    """,
                    (task_id, project_id),
                )
                task = cursor.fetchone()

        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        return task
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )


@router.patch("/{task_id}")
def update_task(
    project_id: int,
    task_id: int,
    updates: TaskUpdate,
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
            detail="Fields cannot be set to null.",
        )

    assignments = ", ".join(f"{field} = %s" for field in changes)
    values = list(changes.values())
    values.extend([task_id, project_id])

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(cursor, project_id, current_user["id"])

                cursor.execute(
                    f"""
                    UPDATE tasks
                    SET {assignments}, updated_at = NOW()
                    WHERE id = %s AND project_id = %s
                    RETURNING *
                    """,
                    values,
                )
                task = cursor.fetchone()

        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        return task
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    project_id: int,
    task_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(cursor, project_id, current_user["id"])

                cursor.execute(
                    """
                    DELETE FROM tasks
                    WHERE id = %s AND project_id = %s
                    RETURNING id
                    """,
                    (task_id, project_id),
                )
                deleted = cursor.fetchone()

        if deleted is None:
            raise HTTPException(status_code=404, detail="Task not found")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )
