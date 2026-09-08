"""Secure customer signature links.

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_signature_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("attestation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attestations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("signed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("attestation_id"), sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_customer_signature_tokens_attestation_id", "customer_signature_tokens", ["attestation_id"])
    op.create_index("ix_customer_signature_tokens_organization_id", "customer_signature_tokens", ["organization_id"])
    op.create_index("ix_customer_signature_tokens_token_hash", "customer_signature_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_table("customer_signature_tokens")
