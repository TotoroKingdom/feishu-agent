"""Add metric snapshots table for T12."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "t12_metric_snapshots"
down_revision = "t11_source_collection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("report_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "normalized_snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("normalized_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("definition_version", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "run_id",
            "normalized_snapshot_id",
            "definition_version",
            "content_hash",
            name="uq_metric_snapshots",
        ),
    )
    op.create_index("ix_metric_snapshots_run_id", "metric_snapshots", ["run_id"])
    op.create_index(
        "ix_metric_snapshots_normalized_snapshot_id",
        "metric_snapshots",
        ["normalized_snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_metric_snapshots_normalized_snapshot_id", table_name="metric_snapshots")
    op.drop_index("ix_metric_snapshots_run_id", table_name="metric_snapshots")
    op.drop_table("metric_snapshots")
