"""Campañas por correo y contactos propios: canal y asunto en la campaña,
destinatarios por canal y dirección, contactos que no son clientes y permiso de
mercadeo por correo con enlace de baja (CAN-SPAM).

Revision ID: 0022
Revises: 0021
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("channel", sa.String(10), nullable=False, server_default="sms"))
    op.add_column("campaigns", sa.Column("subject", sa.String(255)))
    with op.batch_alter_table("campaign_recipients") as b:
        b.add_column(sa.Column("channel", sa.String(10), nullable=False, server_default="sms"))
        b.add_column(sa.Column("email", sa.String(255)))
        b.add_column(sa.Column("subject", sa.String(255)))
        b.add_column(sa.Column("contact_id", GUID()))
        b.add_column(sa.Column("address", sa.String(255), nullable=False, server_default=""))
        b.alter_column("phone", existing_type=sa.String(20), nullable=True)
        b.drop_constraint("uq_campaign_recipient_phone", type_="unique")
    op.execute("UPDATE campaign_recipients SET address = phone WHERE address = ''")
    with op.batch_alter_table("campaign_recipients") as b:
        b.create_unique_constraint("uq_campaign_recipient_address", ["campaign_id", "channel", "address"])
    op.create_table(
        "marketing_contacts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("phone", sa.String(20), index=True),
        sa.Column("email", sa.String(255), index=True),
        sa.Column("notes", sa.String(255)),
        sa.Column("created_by_user_id", GUID()),
    )
    op.create_table(
        "email_marketing_consents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("customer_id", GUID(), index=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("source", sa.String(255)),
        sa.Column("granted_at", sa.DateTime(timezone=True)),
        sa.Column("granted_by_user_id", GUID()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(255)),
        sa.Column("unsubscribe_token", sa.String(64), nullable=False, unique=True),
        sa.UniqueConstraint("organization_id", "email", name="uq_email_consent"),
    )


def downgrade() -> None:
    op.drop_table("email_marketing_consents")
    op.drop_table("marketing_contacts")
    op.execute("DELETE FROM campaign_recipients WHERE channel <> 'sms' OR phone IS NULL")
    with op.batch_alter_table("campaign_recipients") as b:
        b.drop_constraint("uq_campaign_recipient_address", type_="unique")
        b.create_unique_constraint("uq_campaign_recipient_phone", ["campaign_id", "phone"])
        b.alter_column("phone", existing_type=sa.String(20), nullable=False)
        b.drop_column("address")
        b.drop_column("contact_id")
        b.drop_column("subject")
        b.drop_column("email")
        b.drop_column("channel")
    op.drop_column("campaigns", "subject")
    op.drop_column("campaigns", "channel")
