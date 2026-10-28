
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_database_url() -> str:
    """Read the database URL from the environment."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    # Use SQLAlchemy's psycopg 3 driver.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return database_url


def run_migrations_offline() -> None:
    """Configure migrations without opening a database connection."""
    context.configure(
        url=get_database_url(),
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Configure migrations using a live database connection."""
    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 5},
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=None,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
