"""Add LangGraph runtime fields and run history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "t9_langgraph_runtime"
down_revision: str | None = "t8_initial_run_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("report_runs", sa.Column("thread_id", sa.String(128), nullable=True))
    op.add_column(
        "report_runs",
        sa.Column(
            "graph_version",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'weekly_report.v1'"),
        ),
    )
    op.add_column(
        "report_runs",
        sa.Column("state_schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "report_runs",
        sa.Column(
            "current_stage", sa.String(40), nullable=False, server_default=sa.text("'created'")
        ),
    )
    op.add_column("report_runs", sa.Column("current_node", sa.String(80), nullable=True))

    op.execute(
        sa.text("UPDATE report_runs SET thread_id = 'report-run:' || id WHERE thread_id IS NULL")
    )

    op.alter_column("report_runs", "thread_id", nullable=False)
    op.create_unique_constraint("uq_report_runs_thread_id", "report_runs", ["thread_id"])

    op.create_table(
        "run_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("report_runs.id"), nullable=False),
        sa.Column("from_status", sa.String(40), nullable=False),
        sa.Column("to_status", sa.String(40), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("node_name", sa.String(80), nullable=True),
        sa.Column("checkpoint_ref", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_run_status_history_run_id", "run_status_history", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_status_history_run_id", table_name="run_status_history")
    op.drop_table("run_status_history")
    op.drop_constraint("uq_report_runs_thread_id", "report_runs", type_="unique")
    op.drop_column("report_runs", "current_node")
    op.drop_column("report_runs", "current_stage")
    op.drop_column("report_runs", "state_schema_version")
    op.drop_column("report_runs", "graph_version")
    op.drop_column("report_runs", "thread_id")
