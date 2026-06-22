"""add patient identity verification fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import text

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("id_type", sa.String(30), nullable=True))
    op.add_column("patients", sa.Column("id_number", sa.String(100), nullable=True))
    op.add_column("patients", sa.Column("id_document_key", sa.String(500), nullable=True))
    op.add_column(
        "patients",
        sa.Column(
            "identity_verification_status",
            sa.String(20),
            nullable=False,
            server_default=text("'unverified'"),
        ),
    )
    op.add_column("patients", sa.Column("id_rejection_reason", sa.Text(), nullable=True))
    op.add_column(
        "patients",
        sa.Column("id_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_patients_identity_verification_status",
        "patients",
        ["identity_verification_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_patients_identity_verification_status", table_name="patients")
    op.drop_column("patients", "id_verified_at")
    op.drop_column("patients", "id_rejection_reason")
    op.drop_column("patients", "identity_verification_status")
    op.drop_column("patients", "id_document_key")
    op.drop_column("patients", "id_number")
    op.drop_column("patients", "id_type")
