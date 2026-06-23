"""add doctor-initiated scan fields to diagnoses

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "diagnoses",
        sa.Column(
            "uploaded_by_role",
            sa.String(10),
            nullable=False,
            server_default="patient",
        ),
    )
    op.add_column(
        "diagnoses",
        sa.Column(
            "uploading_doctor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("diagnoses", sa.Column("treatment_plan", sa.Text(), nullable=True))
    op.add_column("diagnoses", sa.Column("referral", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("diagnoses", "referral")
    op.drop_column("diagnoses", "treatment_plan")
    op.drop_column("diagnoses", "uploading_doctor_id")
    op.drop_column("diagnoses", "uploaded_by_role")
