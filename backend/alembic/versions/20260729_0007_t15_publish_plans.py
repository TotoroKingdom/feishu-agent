"""Add publish plan table and approved publish plan reference."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "t15_publish_plans"
down_revision = "t13_report_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publish_plans",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("report_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "report_version_id",
            sa.String(length=36),
            sa.ForeignKey("report_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("canonical_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plan_hash", sa.String(length=64), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", "version", name="uq_publish_plans_version"),
        sa.UniqueConstraint("run_id", "plan_hash", name="uq_publish_plans_plan_hash"),
    )
    op.create_index("ix_publish_plans_run_id", "publish_plans", ["run_id"])
    op.create_index("ix_publish_plans_report_version_id", "publish_plans", ["report_version_id"])

    op.add_column(
        "report_runs",
        sa.Column("approved_publish_plan_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_report_runs_approved_publish_plan_id",
        "report_runs",
        ["approved_publish_plan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_runs_approved_publish_plan_id", table_name="report_runs")
    op.drop_column("report_runs", "approved_publish_plan_id")

    op.drop_index("ix_publish_plans_report_version_id", table_name="publish_plans")
    op.drop_index("ix_publish_plans_run_id", table_name="publish_plans")
    op.drop_table("publish_plans")
