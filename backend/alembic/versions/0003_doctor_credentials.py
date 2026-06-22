"""add doctor credentials and registration workflow

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "doctors",
        sa.Column(
            "qualifications", postgresql.JSONB(), nullable=False, server_default=text("'[]'")
        ),
    )
    op.add_column(
        "doctors",
        sa.Column("other_qualifications", sa.Text(), nullable=True),
    )
    op.add_column(
        "doctors",
        sa.Column(
            "certification_keys", postgresql.JSONB(), nullable=False, server_default=text("'[]'")
        ),
    )
    op.add_column(
        "doctors",
        sa.Column(
            "registration_status",
            sa.String(20),
            nullable=False,
            server_default=text("'pending_review'"),
        ),
    )
    op.add_column(
        "doctors",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "doctors",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_doctors_registration_status", "doctors", ["registration_status"])


def downgrade() -> None:
    op.drop_index("ix_doctors_registration_status", table_name="doctors")
    op.drop_column("doctors", "reviewed_at")
    op.drop_column("doctors", "rejection_reason")
    op.drop_column("doctors", "registration_status")
    op.drop_column("doctors", "certification_keys")
    op.drop_column("doctors", "other_qualifications")
    op.drop_column("doctors", "qualifications")
