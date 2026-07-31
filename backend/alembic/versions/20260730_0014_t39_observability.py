"""Add observability execution and audit tables.

Revision ID: t39_observability
Revises: t35_configuration
Create Date: 2026-07-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t39_observability"
down_revision = "t38_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "node_executions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_name", sa.String(length=80), nullable=False),
        sa.Column("node_attempt", sa.Integer(), nullable=False),
        sa.Column("checkpoint_before", sa.String(length=256), nullable=True),
        sa.Column("checkpoint_after", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.JSON(), nullable=False),
        sa.Column("error_class", sa.String(length=128), nullable=True),
        sa.Column("error_summary", sa.String(length=512), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.UniqueConstraint("run_id", "node_name", "node_attempt", name="uq_node_executions_attempt"),
    )
    op.create_index("ix_node_executions_run_id", "node_executions", ["run_id"])
    op.create_index(
        "ix_node_executions_run_started",
        "node_executions",
        ["run_id", "started_at"],
    )

    op.create_table(
        "llm_executions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_execution_id",
            sa.String(length=36),
            sa.ForeignKey("node_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_type", sa.String(length=64), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=36), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_ref", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("schema_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_class", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_llm_executions_run_id", "llm_executions", ["run_id"])
    op.create_index("ix_llm_executions_node_execution_id", "llm_executions", ["node_execution_id"])
    op.create_index(
        "ix_llm_executions_run_created_at",
        "llm_executions",
        ["run_id", "created_at"],
    )
    op.create_index(
        "ix_llm_executions_node_created_at",
        "llm_executions",
        ["node_execution_id", "created_at"],
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("before_summary", sa.JSON(), nullable=False),
        sa.Column("after_summary", sa.JSON(), nullable=False),
        sa.Column("result", sa.String(length=24), nullable=False),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_logs_run_id", "audit_logs", ["run_id"])
    op.create_index("ix_audit_logs_run_occurred", "audit_logs", ["run_id", "occurred_at"])
    op.create_index("ix_audit_logs_actor_occurred", "audit_logs", ["actor_id", "occurred_at"])
    op.create_index("ix_audit_logs_action_occurred", "audit_logs", ["action", "occurred_at"])

    op.create_index(
        "ix_tool_executions_run_started",
        "tool_executions",
        ["run_id", "started_at"],
    )
    op.create_index(
        "ix_tool_executions_tool_status_started",
        "tool_executions",
        ["tool_name", "status", "started_at"],
    )
    op.create_index(
        "ix_tool_executions_node_execution_id",
        "tool_executions",
        ["node_execution_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tool_executions_node_execution_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_tool_status_started", table_name="tool_executions")
    op.drop_index("ix_tool_executions_run_started", table_name="tool_executions")

    op.drop_index("ix_audit_logs_action_occurred", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_occurred", table_name="audit_logs")
    op.drop_index("ix_audit_logs_run_occurred", table_name="audit_logs")
    op.drop_index("ix_audit_logs_run_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_llm_executions_node_created_at", table_name="llm_executions")
    op.drop_index("ix_llm_executions_run_created_at", table_name="llm_executions")
    op.drop_index("ix_llm_executions_node_execution_id", table_name="llm_executions")
    op.drop_index("ix_llm_executions_run_id", table_name="llm_executions")
    op.drop_table("llm_executions")

    op.drop_index("ix_node_executions_run_started", table_name="node_executions")
    op.drop_index("ix_node_executions_run_id", table_name="node_executions")
    op.drop_table("node_executions")
