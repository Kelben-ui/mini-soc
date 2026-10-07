"""complete incident model

Revision ID: 588042e3de4c
Revises: 7c41ecf94c72
Create Date: 2026-10-05 20:51:57.423899
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "588042e3de4c"
down_revision: Union[str, Sequence[str], None] = "7c41ecf94c72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("incident_code", sa.String(length=20), nullable=True)
    )

    op.add_column(
        "incidents",
        sa.Column("affected_hosts", sa.JSON(), nullable=True)
    )

    op.add_column(
        "incidents",
        sa.Column("source_ips", sa.JSON(), nullable=True)
    )

    op.create_table(
        "incident_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.incident_id"),
            nullable=False
        ),
        sa.Column("old_status", sa.String(length=30), nullable=False),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column(
            "changed_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False
        ),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )

    connection = op.get_bind()

    incidents = connection.execute(
        sa.text(
            "SELECT incident_id FROM incidents "
            "ORDER BY incident_id"
        )
    ).fetchall()

    for incident_id, in incidents:
        code = f"INC-{incident_id:04d}"

        connection.execute(
            sa.text(
                "UPDATE incidents "
                "SET incident_code = :code "
                "WHERE incident_id = :incident_id"
            ),
            {
                "code": code,
                "incident_id": incident_id,
            }
        )

    op.alter_column(
        "incidents",
        "incident_code",
        existing_type=sa.String(length=20),
        nullable=False
    )

    op.create_unique_constraint(
        "uq_incidents_incident_code",
        "incidents",
        ["incident_code"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_incidents_incident_code",
        "incidents",
        type_="unique"
    )

    op.drop_table("incident_status_history")

    op.drop_column("incidents", "source_ips")
    op.drop_column("incidents", "affected_hosts")
    op.drop_column("incidents", "incident_code")
