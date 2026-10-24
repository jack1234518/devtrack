
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
    """Create the user and project tables."""
    with get_database_connection() as connection:
        with connection.cursor() as cursor:
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
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )

            # Upgrade an existing projects table without deleting its data.
            cursor.execute(
                """
                ALTER TABLE projects
                ADD COLUMN IF NOT EXISTS user_id INTEGER
                REFERENCES users(id) ON DELETE CASCADE;
                """
            )
