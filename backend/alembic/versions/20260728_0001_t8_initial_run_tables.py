"""Create T8 project and run tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "t8_initial_run_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "project_repositories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("external_id", sa.String(300), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.UniqueConstraint("project_id", "provider", "external_id", name="uq_project_repo"),
    )
    op.create_table(
        "feishu_resources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(300), nullable=False),
        sa.UniqueConstraint("project_id", "resource_type", name="uq_feishu_resource"),
    )
    op.create_table(
        "report_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("period_key", sa.String(120), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "period_key", name="uq_report_runs_project_period"),
    )


def downgrade() -> None:
    op.drop_table("report_runs")
    op.drop_table("feishu_resources")
    op.drop_table("project_repositories")
    op.drop_table("projects")
