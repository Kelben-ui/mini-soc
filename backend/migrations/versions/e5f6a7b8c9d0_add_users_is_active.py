"""add users.is_active (soft delete)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-16 00:00:00.000000

Admins can "delete" a user from the dashboard, but a hard delete would violate
the NOT NULL foreign keys that notes/actions/evidence/custody/status-history
hold on ``users.id`` (and would destroy audit attribution).  Deactivation is a
soft delete instead: the row and its history stay, and the auth layer refuses
to authenticate an inactive user.  Existing rows default to active.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
