"""add action status and executed_at

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-13 00:00:00.000000

The IPS response-action flow (task 4.7) records an intended block, then an
analyst confirms it and the backend executes the helper.  ``status`` tracks
that lifecycle (recorded/executed/failed/unblocked) and ``executed_at`` stamps
when the helper actually ran.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "actions",
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="recorded",
        ),
    )
    op.add_column(
        "actions",
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("actions", "executed_at")
    op.drop_column("actions", "status")
