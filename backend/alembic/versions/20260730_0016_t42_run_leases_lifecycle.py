"""t42 run leases and data lifecycle

Revision ID: t42_run_leases_lifecycle
Revises: t41_onboarding
Create Date: 2026-07-31 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t42_run_leases_lifecycle"
down_revision = "t41_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "report_runs",
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "report_runs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "report_runs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "report_runs",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index(
        "ix_report_runs_status_lease_expires_at",
        "report_runs",
        ["status", "lease_expires_at"],
    )

    op.add_column(
        "side_effect_operations",
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "side_effect_operations",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "side_effect_operations",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_side_effect_operations_status_lease_expires_at",
        "side_effect_operations",
        ["status", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_side_effect_operations_status_lease_expires_at",
        table_name="side_effect_operations",
    )
    op.drop_column("side_effect_operations", "heartbeat_at")
    op.drop_column("side_effect_operations", "lease_expires_at")
    op.drop_column("side_effect_operations", "lease_owner")

    op.drop_index("ix_report_runs_status_lease_expires_at", table_name="report_runs")
    op.drop_column("report_runs", "version")
    op.drop_column("report_runs", "heartbeat_at")
    op.drop_column("report_runs", "lease_expires_at")
    op.drop_column("report_runs", "lease_owner")
