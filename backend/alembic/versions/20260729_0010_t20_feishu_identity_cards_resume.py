"""Add Feishu message delivery ledger."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t20_feishu_identity_cards_resume"
down_revision = "t19_callback_inbox_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feishu_message_deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("report_runs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("onboarding_session_id", sa.String(length=36), nullable=True),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("recipient_type", sa.String(length=16), nullable=False),
        sa.Column("recipient_id", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("external_message_id", sa.String(length=256), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_summary", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_feishu_message_deliveries_idempotency_key"
        ),
        sa.UniqueConstraint(
            "run_id",
            "purpose",
            "revision",
            "recipient_type",
            "recipient_id",
            name="uq_feishu_message_deliveries_run_purpose_revision_recipient",
        ),
    )
    op.create_index(
        "ix_feishu_message_deliveries_status_created_at",
        "feishu_message_deliveries",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_feishu_message_deliveries_run_id", "feishu_message_deliveries", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_feishu_message_deliveries_run_id", table_name="feishu_message_deliveries")
    op.drop_index(
        "ix_feishu_message_deliveries_status_created_at",
        table_name="feishu_message_deliveries",
    )
    op.drop_table("feishu_message_deliveries")
