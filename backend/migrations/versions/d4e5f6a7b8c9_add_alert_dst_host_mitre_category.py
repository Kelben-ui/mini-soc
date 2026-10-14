"""add alert dst_host, mitre and category

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-14 00:00:00.000000

The ``Alert`` ORM model carries ``dst_host`` (task 7.x), ``mitre`` and
``category`` (task 1.7), but the original ``alerts`` table migration
(1aa488fe8300) never created them and no later migration added them either.
Any database built with Alembic was therefore missing the columns, and the
detection loop crashed when it selected ``alerts``.  This migration closes
that schema drift.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("dst_host", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("mitre", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("category", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alerts", "category")
    op.drop_column("alerts", "mitre")
    op.drop_column("alerts", "dst_host")
