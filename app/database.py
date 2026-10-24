
import os

import psycopg
from psycopg.rows import dict_row


def get_database_connection():
    """Open a connection to the PostgreSQL database."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    return psycopg.connect(
        database_url,
        row_factory=dict_row,
    )


def create_tables():
    """Create and safely update the application database tables."""
    with get_database_connection() as connection:
        with connection.cursor() as cursor:

            # 1. Create the users table.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            # 2. Create the projects table.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    description TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'planned'
                        CHECK (
                            status IN (
                                'planned',
                                'in_progress',
                                'completed'
                            )
                        ),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    user_id INTEGER
                        REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )

            # 3. Safely add user_id to an existing projects table.
            cursor.execute(
                """
                ALTER TABLE projects
                ADD COLUMN IF NOT EXISTS user_id INTEGER
                REFERENCES users(id) ON DELETE CASCADE;
                """
            )

            # 4. Create the tasks table with due_date.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    project_id INTEGER NOT NULL
                        REFERENCES projects(id) ON DELETE CASCADE,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'todo'
                        CHECK (
                            status IN (
                                'todo',
                                'in_progress',
                                'completed'
                            )
                        ),
                    due_date DATE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            # 5. Safely add due_date to existing tasks tables.
            # Existing tasks are preserved; their due_date will be NULL.
            cursor.execute(
                """
                ALTER TABLE tasks
                ADD COLUMN IF NOT EXISTS due_date DATE;
                """
            )
