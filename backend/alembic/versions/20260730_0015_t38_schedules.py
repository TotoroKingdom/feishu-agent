"""Add weekly schedule configuration table.

Revision ID: t38_schedules
Revises: t37_admin_auth
Create Date: 2026-07-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t38_schedules"
down_revision = "t37_admin_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_configs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("cron_expression", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "misfire_policy",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'fire_once'"),
        ),
        sa.Column("next_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", name="uq_schedule_configs_project_id"),
    )
    op.create_index("ix_schedule_configs_project_id", "schedule_configs", ["project_id"])
    op.create_index(
        "ix_schedule_configs_enabled_next_fire_at",
        "schedule_configs",
        ["enabled", "next_fire_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_schedule_configs_enabled_next_fire_at", table_name="schedule_configs")
    op.drop_index("ix_schedule_configs_project_id", table_name="schedule_configs")
    op.drop_table("schedule_configs")
