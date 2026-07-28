"""Add HITL 1 generation approvals."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "t10_generation_approvals"
down_revision: str | None = "t9_langgraph_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "report_runs",
        sa.Column("scope_revision", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "human_approvals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("approval_type", sa.String(length=24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("challenge_id", sa.String(length=36), nullable=False),
        sa.Column("card_message_id", sa.String(length=128), nullable=True),
        sa.Column("requested_from", sa.JSON(), nullable=False),
        sa.Column("request_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("plan_hash", sa.String(length=64), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("supplement", sa.JSON(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "approval_type", "revision", name="uq_human_approvals_revision"),
        sa.UniqueConstraint("challenge_id", name="uq_human_approvals_challenge_id"),
    )
    op.create_index("ix_human_approvals_run_id", "human_approvals", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_human_approvals_run_id", table_name="human_approvals")
    op.drop_table("human_approvals")
    op.drop_column("report_runs", "scope_revision")
