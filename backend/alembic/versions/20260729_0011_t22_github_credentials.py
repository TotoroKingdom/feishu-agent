"""Add encrypted GitHub credential storage."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t22_github_credentials"
down_revision = "t20_feishu_identity_cards_resume"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "encrypted_credentials",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("credential_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.String(length=32), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("updated_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "credential_type", "label", name="uq_encrypted_credentials_label"),
        sa.UniqueConstraint("fingerprint", name="uq_encrypted_credentials_fingerprint"),
    )
    op.create_index(
        "ix_encrypted_credentials_project_type_status",
        "encrypted_credentials",
        ["project_id", "credential_type", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_encrypted_credentials_project_type_status",
        table_name="encrypted_credentials",
    )
    op.drop_table("encrypted_credentials")
