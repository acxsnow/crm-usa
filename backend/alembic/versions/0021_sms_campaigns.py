"""Campañas de SMS de productos: catálogo libre de productos, permiso de
mercadeo por número (TCPA), campañas y su lista de envío.

Revision ID: 0021
Revises: 0020
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("price", sa.String(50)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "marketing_consents",
        sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("customer_id", GUID(), index=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("source", sa.String(255)),
        sa.Column("granted_at", sa.DateTime(timezone=True)),
        sa.Column("granted_by_user_id", GUID()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(255)),
        sa.UniqueConstraint("organization_id", "phone", name="uq_marketing_consent_phone"),
    )
    op.create_table(
        "campaigns",
        sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("product_id", GUID(), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("audience", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", GUID()),
    )
    op.create_table(
        "campaign_recipients",
        sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("campaign_id", GUID(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("customer_id", GUID()),
        sa.Column("name", sa.String(255)),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("timezone", sa.String(40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("campaign_id", "phone", name="uq_campaign_recipient_phone"),
    )
    op.create_index("ix_campaign_recipients_queue", "campaign_recipients", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_campaign_recipients_queue", table_name="campaign_recipients")
    op.drop_table("campaign_recipients")
    op.drop_table("campaigns")
    op.drop_table("marketing_consents")
    op.drop_table("products")
