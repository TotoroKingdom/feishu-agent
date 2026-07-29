"""Add source collection, normalized snapshot and validation tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "t11_source_collection"
down_revision: str | None = "t10_generation_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_data_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_resource_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("cursor", sa.String(length=512), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("fetch_status", sa.String(length=20), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "run_id",
            "source_type",
            "source_resource_id",
            "entity_type",
            "page_no",
            "payload_hash",
            name="uq_source_data_batches_identity",
        ),
    )
    op.create_index("ix_source_data_batches_run_id", "source_data_batches", ["run_id"])
    op.create_index(
        "ix_source_data_batches_run_entity",
        "source_data_batches",
        ["run_id", "entity_type"],
    )
    op.create_index("ix_source_data_batches_expires_at", "source_data_batches", ["expires_at"])

    op.create_table(
        "normalized_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_batch_set_hash", sa.String(length=64), nullable=False),
        sa.Column("mapping_revision", sa.String(length=32), nullable=False),
        sa.Column("normalizer_version", sa.String(length=32), nullable=False),
        sa.Column("entity_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "content_hash", name="uq_normalized_snapshots"),
    )
    op.create_index("ix_normalized_snapshots_run_id", "normalized_snapshots", ["run_id"])

    op.create_table(
        "normalized_entities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "normalized_snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("normalized_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("source_resource_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=True),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=True),
        sa.Column("author_external_id", sa.String(length=128), nullable=True),
        sa.Column("assignee_external_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("milestone_external_id", sa.String(length=128), nullable=True),
        sa.Column("created_at_external", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_external", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at_external", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_batch_id", sa.String(length=36), nullable=True),
        sa.Column("raw_summary", sa.String(length=512), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id",
            "source_type",
            "source_resource_id",
            "entity_type",
            "external_id",
            "content_hash",
            name="uq_normalized_entities_identity",
        ),
    )
    op.create_index("ix_normalized_entities_run_id", "normalized_entities", ["run_id"])
    op.create_index(
        "ix_normalized_entities_snapshot", "normalized_entities", ["normalized_snapshot_id"]
    )

    op.create_table(
        "validation_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("validation_pass", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("data_quality_status", sa.String(length=24), nullable=False),
        sa.Column("rule_set_version", sa.String(length=32), nullable=False),
        sa.Column("critical_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("missing_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conflicts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "input_snapshot_hash", name="uq_validation_results"),
    )
    op.create_index("ix_validation_results_run_created", "validation_results", ["run_id", "created_at"])

    op.create_table(
        "tool_executions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_execution_id", sa.String(length=128), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("tool_version", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_ref", sa.String(length=36), nullable=True),
        sa.Column("provider_request_id", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_class", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.UniqueConstraint("run_id", "idempotency_key", "attempt", name="uq_tool_executions_attempt"),
    )
    op.create_index("ix_tool_executions_run_id", "tool_executions", ["run_id"])
    op.create_index("ix_tool_executions_tool_status", "tool_executions", ["tool_name", "status"])


def downgrade() -> None:
    op.drop_index("ix_tool_executions_tool_status", table_name="tool_executions")
    op.drop_index("ix_tool_executions_run_id", table_name="tool_executions")
    op.drop_table("tool_executions")

    op.drop_index("ix_validation_results_run_created", table_name="validation_results")
    op.drop_table("validation_results")

    op.drop_index("ix_normalized_entities_snapshot", table_name="normalized_entities")
    op.drop_index("ix_normalized_entities_run_id", table_name="normalized_entities")
    op.drop_table("normalized_entities")

    op.drop_index("ix_normalized_snapshots_run_id", table_name="normalized_snapshots")
    op.drop_table("normalized_snapshots")

    op.drop_index("ix_source_data_batches_expires_at", table_name="source_data_batches")
    op.drop_index("ix_source_data_batches_run_entity", table_name="source_data_batches")
    op.drop_index("ix_source_data_batches_run_id", table_name="source_data_batches")
    op.drop_table("source_data_batches")
