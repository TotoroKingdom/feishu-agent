"""Add callback inbox and transactional outbox tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "t19_callback_inbox_outbox"
down_revision = "t16_side_effect_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "callback_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_event_id", sa.String(length=256), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_class", sa.String(length=128), nullable=True),
        sa.Column("last_error_summary", sa.String(length=512), nullable=True),
        sa.UniqueConstraint(
            "provider", "external_event_id", name="uq_callback_events_provider_event_id"
        ),
    )
    op.create_index("ix_callback_events_run_id", "callback_events", ["run_id"])
    op.create_index(
        "ix_callback_events_status_received_at", "callback_events", ["status", "received_at"]
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_request_id", sa.String(length=256), nullable=True),
        sa.Column("external_message_id", sa.String(length=256), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_class", sa.String(length=128), nullable=True),
        sa.Column("last_error_summary", sa.String(length=512), nullable=True),
        sa.UniqueConstraint("dedupe_key", name="uq_outbox_messages_dedupe_key"),
    )
    op.create_index(
        "ix_outbox_messages_status_available_at",
        "outbox_messages",
        ["status", "available_at"],
    )
    op.create_index("ix_outbox_messages_topic", "outbox_messages", ["topic"])


def downgrade() -> None:
    op.drop_index("ix_outbox_messages_topic", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_status_available_at", table_name="outbox_messages")
    op.drop_table("outbox_messages")

    op.drop_index("ix_callback_events_status_received_at", table_name="callback_events")
    op.drop_index("ix_callback_events_run_id", table_name="callback_events")
    op.drop_table("callback_events")
