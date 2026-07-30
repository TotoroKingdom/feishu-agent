"""Add diagnosis records for controlled agent loop."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t30_diagnosis_records"
down_revision = "t22_github_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnosis_records",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "validation_result_id",
            sa.String(length=36),
            sa.ForeignKey("validation_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("problem_key", sa.String(length=128), nullable=False),
        sa.Column("problem_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("observation", sa.JSON(), nullable=False),
        sa.Column("diagnosis", sa.JSON(), nullable=False),
        sa.Column("impact_scope", sa.JSON(), nullable=False),
        sa.Column("recoverability", sa.String(length=24), nullable=False),
        sa.Column("planned_action", sa.String(length=64), nullable=False),
        sa.Column("action_params", sa.JSON(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=24), nullable=False),
        sa.Column("next_node", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", "problem_key", "attempt", name="uq_diagnosis_records_attempt"),
    )
    op.create_index(
        "ix_diagnosis_records_run_created_at",
        "diagnosis_records",
        ["run_id", "created_at"],
    )
    op.create_index("ix_diagnosis_records_run_id", "diagnosis_records", ["run_id"])
    op.create_index(
        "ix_diagnosis_records_validation_result_id",
        "diagnosis_records",
        ["validation_result_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_diagnosis_records_validation_result_id", table_name="diagnosis_records")
    op.drop_index("ix_diagnosis_records_run_id", table_name="diagnosis_records")
    op.drop_index("ix_diagnosis_records_run_created_at", table_name="diagnosis_records")
    op.drop_table("diagnosis_records")
