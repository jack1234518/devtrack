
import logging
import os

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


def get_database_connection():
    """Open a connection to PostgreSQL with a timeout."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    try:
        return psycopg.connect(
            database_url,
            row_factory=dict_row,
            connect_timeout=5,
            application_name="devtrack-api",
        )
    except psycopg.Error:
        logger.exception("Failed to connect to the PostgreSQL database.")
        raise


def create_tables():
    """Create tables and safely apply existing schema updates."""
    with get_database_connection() as connection:
        with connection.cursor() as cursor:

            # Users
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

            # Projects
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

            # Migration for existing projects.
            cursor.execute(
                """
                ALTER TABLE projects
                ADD COLUMN IF NOT EXISTS user_id INTEGER
                REFERENCES users(id) ON DELETE CASCADE;
                """
            )

            # Tasks
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
                    priority VARCHAR(10) NOT NULL DEFAULT 'medium'
                        CHECK (
                            priority IN ('low', 'medium', 'high')
                        ),
                    due_date DATE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            # Migrations for existing tasks.
            cursor.execute(
                """
                ALTER TABLE tasks
                ADD COLUMN IF NOT EXISTS due_date DATE;
                """
            )

            cursor.execute(
                """
                ALTER TABLE tasks
                ADD COLUMN IF NOT EXISTS priority VARCHAR(10)
                NOT NULL DEFAULT 'medium';
                """
            )

            # Ensure priorities are restricted to valid values.
            cursor.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'tasks_priority_check'
                          AND conrelid = 'tasks'::regclass
                    ) THEN
                        ALTER TABLE tasks
                        ADD CONSTRAINT tasks_priority_check
                        CHECK (priority IN ('low', 'medium', 'high'));
                    END IF;
                END
                $$;
                """
            )

    logger.info("Database tables and schema checks completed.")
