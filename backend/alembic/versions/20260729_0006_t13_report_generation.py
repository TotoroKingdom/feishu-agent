"""Add report generation and evidence chain tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "t13_report_generation"
down_revision = "t12_metric_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_sets",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("report_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "normalized_snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("normalized_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("metric_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("builder_version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "content_hash", name="uq_evidence_sets"),
    )
    op.create_index("ix_evidence_sets_run_id", "evidence_sets", ["run_id"])
    op.create_index("ix_evidence_sets_normalized_snapshot_id", "evidence_sets", ["normalized_snapshot_id"])
    op.create_index("ix_evidence_sets_metric_snapshot_id", "evidence_sets", ["metric_snapshot_id"])

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "evidence_set_id",
            sa.String(length=36),
            sa.ForeignKey("evidence_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_key", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_resource_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_summary", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "normalized_entity_id",
            sa.String(length=36),
            sa.ForeignKey("normalized_entities.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("evidence_set_id", "evidence_key", name="uq_evidence_items"),
    )
    op.create_index("ix_evidence_items_evidence_set_id", "evidence_items", ["evidence_set_id"])
    op.create_index("ix_evidence_items_normalized_entity_id", "evidence_items", ["normalized_entity_id"])

    op.create_table(
        "report_versions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("report_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("structured_report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("structured_hash", sa.String(length=64), nullable=False),
        sa.Column("rendered_content", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt_version_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("data_quality_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", "version", name="uq_report_versions_version"),
        sa.UniqueConstraint("run_id", "content_hash", name="uq_report_versions_content_hash"),
    )
    op.create_index("ix_report_versions_run_id", "report_versions", ["run_id"])

    op.create_table(
        "report_claims",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "report_version_id",
            sa.String(length=36),
            sa.ForeignKey("report_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_key", sa.String(length=128), nullable=False),
        sa.Column("content", sa.String(length=1024), nullable=False),
        sa.Column("claim_type", sa.String(length=24), nullable=False),
        sa.Column("importance", sa.String(length=24), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("grounding_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("report_version_id", "claim_key", name="uq_report_claims"),
    )
    op.create_index("ix_report_claims_report_version_id", "report_claims", ["report_version_id"])

    op.create_table(
        "report_evidence",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "claim_id",
            sa.String(length=36),
            sa.ForeignKey("report_claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_item_id",
            sa.String(length=36),
            sa.ForeignKey("evidence_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("citation_order", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("claim_id", "evidence_item_id", name="uq_report_evidence"),
    )
    op.create_index("ix_report_evidence_claim_id", "report_evidence", ["claim_id"])
    op.create_index("ix_report_evidence_evidence_item_id", "report_evidence", ["evidence_item_id"])
    op.create_index("ix_report_evidence_claim_order", "report_evidence", ["claim_id", "citation_order"])


def downgrade() -> None:
    op.drop_index("ix_report_evidence_claim_order", table_name="report_evidence")
    op.drop_index("ix_report_evidence_evidence_item_id", table_name="report_evidence")
    op.drop_index("ix_report_evidence_claim_id", table_name="report_evidence")
    op.drop_table("report_evidence")

    op.drop_index("ix_report_claims_report_version_id", table_name="report_claims")
    op.drop_table("report_claims")

    op.drop_index("ix_report_versions_run_id", table_name="report_versions")
    op.drop_table("report_versions")

    op.drop_index("ix_evidence_items_normalized_entity_id", table_name="evidence_items")
    op.drop_index("ix_evidence_items_evidence_set_id", table_name="evidence_items")
    op.drop_table("evidence_items")

    op.drop_index("ix_evidence_sets_metric_snapshot_id", table_name="evidence_sets")
    op.drop_index("ix_evidence_sets_normalized_snapshot_id", table_name="evidence_sets")
    op.drop_index("ix_evidence_sets_run_id", table_name="evidence_sets")
    op.drop_table("evidence_sets")
