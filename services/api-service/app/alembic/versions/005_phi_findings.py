"""phi_findings

Revision ID: 005
Revises: 004
Create Date: 2026-05-27

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phi_findings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("audit_event_id", sa.Uuid(), nullable=False),
        sa.Column("tag", sa.String(length=9), nullable=False),
        sa.Column("tag_name", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("value_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"],
            ["audit_events.event_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_phi_findings_audit_event_id",
        "phi_findings",
        ["audit_event_id"],
    )
    op.create_index(
        "idx_phi_findings_severity",
        "phi_findings",
        ["severity"],
    )


def downgrade() -> None:
    op.drop_index("idx_phi_findings_severity", table_name="phi_findings")
    op.drop_index("idx_phi_findings_audit_event_id", table_name="phi_findings")
    op.drop_table("phi_findings")
