"""Add side effect ledger and report artifact tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "t16_side_effect_ledger"
down_revision = "t15_publish_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "side_effect_operations",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "publish_plan_id",
            sa.String(length=36),
            sa.ForeignKey("publish_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("target_ref", sa.String(length=512), nullable=False),
        sa.Column("target_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_ref", sa.String(length=512), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("external_resource_id", sa.String(length=256), nullable=True),
        sa.Column("external_url", sa.String(length=512), nullable=True),
        sa.Column("provider_request_id", sa.String(length=256), nullable=True),
        sa.Column("verification_status", sa.String(length=24), nullable=True),
        sa.Column("last_error_class", sa.String(length=128), nullable=True),
        sa.Column("last_error_summary", sa.String(length=512), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("publish_plan_id", "sequence", name="uq_side_effect_operations_sequence"),
        sa.UniqueConstraint("idempotency_key", name="uq_side_effect_operations_idempotency_key"),
    )
    op.create_index("ix_side_effect_operations_publish_plan_id", "side_effect_operations", ["publish_plan_id"])
    op.create_index("ix_side_effect_operations_run_id", "side_effect_operations", ["run_id"])
    op.create_index("ix_side_effect_operations_run_status", "side_effect_operations", ["run_id", "status"])

    op.create_table(
        "side_effect_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "operation_id",
            sa.String(length=36),
            sa.ForeignKey("side_effect_operations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("request_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider_request_id", sa.String(length=256), nullable=True),
        sa.Column("response_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_class", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("operation_id", "attempt", name="uq_side_effect_attempts"),
    )
    op.create_index("ix_side_effect_attempts_operation_id", "side_effect_attempts", ["operation_id"])

    op.create_table(
        "report_artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_version_id",
            sa.String(length=36),
            sa.ForeignKey("report_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column(
            "operation_id",
            sa.String(length=36),
            sa.ForeignKey("side_effect_operations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("target_ref", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("operation_id", name="uq_report_artifacts_operation"),
    )
    op.create_index("ix_report_artifacts_run_id", "report_artifacts", ["run_id"])
    op.create_index("ix_report_artifacts_report_version_id", "report_artifacts", ["report_version_id"])
    op.create_index("ix_report_artifacts_operation_id", "report_artifacts", ["operation_id"])
    op.create_index("ix_report_artifacts_run_type", "report_artifacts", ["run_id", "artifact_type"])


def downgrade() -> None:
    op.drop_index("ix_report_artifacts_run_type", table_name="report_artifacts")
    op.drop_index("ix_report_artifacts_operation_id", table_name="report_artifacts")
    op.drop_index("ix_report_artifacts_report_version_id", table_name="report_artifacts")
    op.drop_index("ix_report_artifacts_run_id", table_name="report_artifacts")
    op.drop_table("report_artifacts")

    op.drop_index("ix_side_effect_attempts_operation_id", table_name="side_effect_attempts")
    op.drop_table("side_effect_attempts")

    op.drop_index("ix_side_effect_operations_run_status", table_name="side_effect_operations")
    op.drop_index("ix_side_effect_operations_run_id", table_name="side_effect_operations")
    op.drop_index("ix_side_effect_operations_publish_plan_id", table_name="side_effect_operations")
    op.drop_table("side_effect_operations")
