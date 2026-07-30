"""Add configuration and connectivity tables.

Revision ID: t35_configuration
Revises: t30_diagnosis_records
Create Date: 2026-07-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t35_configuration"
down_revision = "t30_diagnosis_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("prompt_type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("model_constraints", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("prompt_type", "version", name="uq_prompt_versions_type_version"),
    )
    op.create_index(
        "ix_prompt_versions_type_status",
        "prompt_versions",
        ["prompt_type", "status"],
    )

    op.create_table(
        "model_configs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("stream", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("scope", name="uq_model_configs_scope"),
    )

    op.create_table(
        "feishu_field_mappings",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "resource_id",
            sa.String(length=36),
            sa.ForeignKey("feishu_resources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("logical_field", sa.String(length=128), nullable=False),
        sa.Column("external_field_id", sa.String(length=128), nullable=False),
        sa.Column("external_field_name", sa.String(length=256), nullable=True),
        sa.Column("external_field_type", sa.String(length=64), nullable=True),
        sa.Column("converter", sa.String(length=64), nullable=True),
        sa.Column("required_level", sa.String(length=16), nullable=False),
        sa.Column("mapping_options", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("resource_id", "logical_field", name="uq_feishu_field_mappings_logical"),
        sa.UniqueConstraint(
            "resource_id", "external_field_id", name="uq_feishu_field_mappings_external"
        ),
    )
    op.create_index(
        "ix_feishu_field_mappings_resource_id",
        "feishu_field_mappings",
        ["resource_id"],
    )

    op.create_table(
        "async_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_summary", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "job_type", "requested_by", "request_hash", name="uq_async_jobs_request"
        ),
    )
    op.create_index("ix_async_jobs_status_created", "async_jobs", ["status", "created_at"])

    op.add_column("projects", sa.Column("description", sa.String(length=512), nullable=True))
    op.add_column(
        "projects",
        sa.Column(
            "default_period_rule",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "projects",
        sa.Column("default_prompt_version_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "projects",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column("project_repositories", sa.Column("owner", sa.String(length=128), nullable=True))
    op.add_column("project_repositories", sa.Column("repo", sa.String(length=128), nullable=True))
    op.add_column(
        "project_repositories",
        sa.Column("repository_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "project_repositories",
        sa.Column("weight", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "project_repositories",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "project_repositories",
        sa.Column("default_branch", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "project_repositories",
        sa.Column("last_connectivity_status", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "project_repositories",
        sa.Column("last_connectivity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_repositories",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "project_repositories",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column("feishu_resources", sa.Column("name", sa.String(length=256), nullable=True))
    op.add_column("feishu_resources", sa.Column("schema_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "feishu_resources",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "feishu_resources",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "feishu_resources",
        sa.Column("last_connectivity_status", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "feishu_resources",
        sa.Column("last_connectivity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "feishu_resources",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("feishu_resources", "updated_at")
    op.drop_column("feishu_resources", "last_connectivity_at")
    op.drop_column("feishu_resources", "last_connectivity_status")
    op.drop_column("feishu_resources", "revision")
    op.drop_column("feishu_resources", "enabled")
    op.drop_column("feishu_resources", "schema_hash")
    op.drop_column("feishu_resources", "name")

    op.drop_column("project_repositories", "updated_at")
    op.drop_column("project_repositories", "revision")
    op.drop_column("project_repositories", "last_connectivity_at")
    op.drop_column("project_repositories", "last_connectivity_status")
    op.drop_column("project_repositories", "default_branch")
    op.drop_column("project_repositories", "enabled")
    op.drop_column("project_repositories", "weight")
    op.drop_column("project_repositories", "repository_type")
    op.drop_column("project_repositories", "repo")
    op.drop_column("project_repositories", "owner")

    op.drop_column("projects", "updated_at")
    op.drop_column("projects", "revision")
    op.drop_column("projects", "default_prompt_version_id")
    op.drop_column("projects", "default_period_rule")
    op.drop_column("projects", "description")

    op.drop_index("ix_async_jobs_status_created", table_name="async_jobs")
    op.drop_table("async_jobs")

    op.drop_index("ix_feishu_field_mappings_resource_id", table_name="feishu_field_mappings")
    op.drop_table("feishu_field_mappings")

    op.drop_table("model_configs")

    op.drop_index("ix_prompt_versions_type_status", table_name="prompt_versions")
    op.drop_table("prompt_versions")
