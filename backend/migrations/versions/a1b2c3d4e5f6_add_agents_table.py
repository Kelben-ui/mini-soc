"""add agents table

Revision ID: a1b2c3d4e5f6
Revises: 588042e3de4c
Create Date: 2026-10-13 00:00:00.000000

The ``agents`` table backs the log-agent heartbeat endpoint added for task
3.7 (``POST /api/agents/heartbeat``).  The ORM model existed but no migration
was ever written, so on a real (alembic-managed) database the table was
missing.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "588042e3de4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="offline",
        ),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.UniqueConstraint("name", name="uq_agents_name"),
    )


def downgrade() -> None:
    op.drop_table("agents")
