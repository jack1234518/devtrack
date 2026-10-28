
"""Create the initial DevTrack database schema."""

from alembic import op
import sqlalchemy as sa


# Identifiers used by Alembic.
revision = "a2e1864892c3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables for a fresh DevTrack database."""

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=True),
            primary_key=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="users_email_key"),
    )

    op.create_table(
        "projects",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=True),
            primary_key=True,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'planned'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed')",
            name="projects_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="projects_user_id_fkey",
        ),
    )

    op.create_table(
        "tasks",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=True),
            primary_key=True,
        ),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'todo'"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(10),
            server_default=sa.text("'medium'"),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'completed')",
            name="tasks_status_check",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="tasks_priority_check",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="tasks_project_id_fkey",
        ),
    )


def downgrade() -> None:
    """Remove the schema created by this migration."""

    op.drop_table("tasks")
    op.drop_table("projects")
    op.drop_table("users")
