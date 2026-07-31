"""Add onboarding sessions table.

Revision ID: t41_onboarding
Revises: t39_observability
Create Date: 2026-07-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t41_onboarding"
down_revision = "t39_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onboarding_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("feishu_actor_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_step", sa.String(length=64), nullable=False),
        sa.Column("draft_config", sa.JSON(), nullable=False),
        sa.Column(
            "credential_ref",
            sa.String(length=36),
            sa.ForeignKey("encrypted_credentials.id"),
            nullable=True,
        ),
        sa.Column("card_message_id", sa.String(length=128), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_onboarding_sessions_actor_status",
        "onboarding_sessions",
        ["feishu_actor_id", "status"],
    )
    op.create_index(
        "uq_onboarding_sessions_active_actor",
        "onboarding_sessions",
        ["feishu_actor_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('in_progress', 'pending_confirmation')"),
        postgresql_where=sa.text("status IN ('in_progress', 'pending_confirmation')"),
    )
    op.create_index(
        "ix_onboarding_sessions_credential_ref",
        "onboarding_sessions",
        ["credential_ref"],
    )


def downgrade() -> None:
    op.drop_index("ix_onboarding_sessions_credential_ref", table_name="onboarding_sessions")
    op.drop_index("uq_onboarding_sessions_active_actor", table_name="onboarding_sessions")
    op.drop_index("ix_onboarding_sessions_actor_status", table_name="onboarding_sessions")
    op.drop_table("onboarding_sessions")
