"""add incident contained_at and resolved_at

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-14 00:00:00.000000

Task 7.8 renders TTC/TTR on the incident header.  The ``Incident`` ORM model
has carried ``contained_at``/``resolved_at`` since the model was completed, but
no migration ever created those columns, so a database upgraded with Alembic
was missing them.  This migration closes that schema drift.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("contained_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "resolved_at")
    op.drop_column("incidents", "contained_at")
