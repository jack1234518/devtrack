
from datetime import date
from math import ceil
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.database import get_database_connection
from app.dependencies import get_current_user


router = APIRouter(
    prefix="/projects/{project_id}/tasks",
    tags=["Tasks"],
)

TaskStatus = Literal["todo", "in_progress", "completed"]
TaskPriority = Literal["low", "medium", "high"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus = "todo"
    due_date: date | None = None
    priority: TaskPriority = "medium"


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    due_date: date | None = None
    priority: TaskPriority | None = None


def ensure_project_owner(cursor, project_id: int, user_id: int):
    """Only allow the owner to access a project's tasks."""
    cursor.execute(
        """
        SELECT id
        FROM projects
        WHERE id = %s AND user_id = %s
        """,
        (project_id, user_id),
    )

    if cursor.fetchone() is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )


def task_response(task: dict) -> dict:
    """Add a calculated overdue flag to a task."""
    task["is_overdue"] = (
        task["due_date"] is not None
        and task["due_date"] < date.today()
        and task["status"] != "completed"
    )
    return task


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int,
    task: TaskCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(
                    cursor, project_id, current_user["id"]
                )

                cursor.execute(
                    """
                    INSERT INTO tasks (
                        project_id,
                        title,
                        description,
                        status,
                        due_date,
                        priority
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        project_id,
                        task.title,
                        task.description,
                        task.status,
                        task.due_date,
                        task.priority,
                    ),
                )
                created_task = cursor.fetchone()

        return task_response(created_task)

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )


@router.get("")
def list_tasks(
    project_id: int,
    task_status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    overdue: bool = False,
    search: str | None = Query(default=None, min_length=1, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Filter, search, sort, and paginate tasks for an owned project."""
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(
                    cursor, project_id, current_user["id"]
                )

                conditions = ["project_id = %s"]
                parameters: list = [project_id]

                if task_status is not None:
                    conditions.append("status = %s")
                    parameters.append(task_status)

                if priority is not None:
                    conditions.append("priority = %s")
                    parameters.append(priority)

                if overdue:
                    conditions.append(
                        """
                        due_date < CURRENT_DATE
                        AND status != 'completed'
                        """
                    )

                if search is not None:
                    conditions.append("title ILIKE %s")
                    parameters.append(f"%{search.strip()}%")

                where_clause = " AND ".join(conditions)

                # Count matching tasks before applying pagination.
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM tasks
                    WHERE {where_clause}
                    """,
                    parameters,
                )
                total = cursor.fetchone()["total"]

                offset = (page - 1) * page_size

                cursor.execute(
                    f"""
                    SELECT *
                    FROM tasks
                    WHERE {where_clause}
                    ORDER BY
                        CASE priority
                            WHEN 'high' THEN 1
                            WHEN 'medium' THEN 2
                            WHEN 'low' THEN 3
                        END,
                        CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                        due_date ASC,
                        id ASC
                    LIMIT %s OFFSET %s
                    """,
                    parameters + [page_size, offset],
                )
                tasks = cursor.fetchall()

        total_pages = ceil(total / page_size) if total else 0

        return {
            "items": [task_response(task) for task in tasks],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1 and total_pages > 0,
        }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )


@router.get("/overdue")
def list_overdue_tasks(
    project_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Return all unfinished tasks whose deadlines have passed."""
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(
                    cursor, project_id, current_user["id"]
                )

                cursor.execute(
                    """
                    SELECT *
                    FROM tasks
                    WHERE project_id = %s
                      AND due_date < CURRENT_DATE
                      AND status != 'completed'
                    ORDER BY due_date ASC, id ASC
                    """,
                    (project_id,),
                )
                tasks = cursor.fetchall()

        return [task_response(task) for task in tasks]

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
                ensure_project_owner(
                    cursor, project_id, current_user["id"]
                )

                cursor.execute(
                    """
                    SELECT *
                    FROM tasks
                    WHERE id = %s AND project_id = %s
                    """,
                    (task_id, project_id),
                )
                task = cursor.fetchone()

        if task is None:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return task_response(task)

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

    nullable_fields = {"description", "due_date"}

    if any(
        value is None and field not in nullable_fields
        for field, value in changes.items()
    ):
        raise HTTPException(
            status_code=422,
            detail="Title, status, and priority cannot be set to null.",
        )

    assignments = ", ".join(
        f"{field} = %s" for field in changes
    )
    values = list(changes.values())
    values.extend([task_id, project_id])

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(
                    cursor, project_id, current_user["id"]
                )

                cursor.execute(
                    f"""
                    UPDATE tasks
                    SET {assignments}, updated_at = NOW()
                    WHERE id = %s AND project_id = %s
                    RETURNING *
                    """,
                    values,
                )
                updated_task = cursor.fetchone()

        if updated_task is None:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return task_response(updated_task)

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task(
    project_id: int,
    task_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                ensure_project_owner(
                    cursor, project_id, current_user["id"]
                )

                cursor.execute(
                    """
                    DELETE FROM tasks
                    WHERE id = %s AND project_id = %s
                    RETURNING id
                    """,
                    (task_id, project_id),
                )
                deleted_task = cursor.fetchone()

        if deleted_task is None:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed.",
        )
