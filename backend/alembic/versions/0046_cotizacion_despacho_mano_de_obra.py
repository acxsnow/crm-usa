"""Cotización por enlace con opciones y firma, tarifa por hora de cada técnico
y campañas automáticas por evento. Spec
`2026-10-31-cotizacion-despacho-mano-de-obra-automatizaciones-design.md`.

- `quotes`: opciones (básica / mejor / premium), opción aceptada, enlace
  público, firma del cliente y quién decidió. `quote_lines.option_key`.
- `labor_rates`: costo de una hora por técnico.
- `campaign_automations` y `campaign_automation_sends`.

Sin permisos nuevos: usan `quotes.manage`, `budgets.manage`,
`notifications.manage` y `dispatch.manage`.

Revision ID: 0046
Revises: 0045
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(12, 2)


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.add_column("quotes", sa.Column("options", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("quotes", sa.Column("accepted_option", sa.String(10)))
    op.add_column("quotes", sa.Column("public_token_hash", sa.String(128)))
    op.add_column("quotes", sa.Column("public_sent_to", sa.String(255)))
    op.add_column("quotes", sa.Column("viewed_at", sa.DateTime(timezone=True)))
    op.add_column("quotes", sa.Column("signer_name", sa.String(255)))
    op.add_column("quotes", sa.Column("signature_path", sa.String(500)))
    op.add_column("quotes", sa.Column("signed_ip", sa.String(64)))
    op.add_column("quotes", sa.Column("decided_by", sa.String(20)))
    op.create_index("ix_quotes_public_token_hash", "quotes", ["public_token_hash"], unique=True)
    op.add_column("quote_lines", sa.Column("option_key", sa.String(10)))

    op.create_table(
        "labor_rates", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hourly_rate", MONEY, nullable=False),
        sa.Column("updated_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_labor_rate_user"),
    )
    op.create_table(
        "campaign_automations", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trigger", sa.String(30), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("channel", sa.String(10), nullable=False, server_default="sms"),
        sa.Column("subject", sa.String(255)),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("starts_on", sa.DateTime(timezone=True), nullable=False),
        sa.Column("campaign_id", GUID(), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("created_by_user_id", GUID()),
    )
    op.create_table(
        "campaign_automation_sends", sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("automation_id", GUID(), sa.ForeignKey("campaign_automations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("automation_id", "project_id", name="uq_automation_project"),
    )


def downgrade() -> None:
    op.drop_table("campaign_automation_sends")
    op.drop_table("campaign_automations")
    op.drop_table("labor_rates")
    op.drop_column("quote_lines", "option_key")
    op.drop_index("ix_quotes_public_token_hash", table_name="quotes")
    for col in ("decided_by", "signed_ip", "signature_path", "signer_name", "viewed_at", "public_sent_to",
                "public_token_hash", "accepted_option", "options"):
        op.drop_column("quotes", col)
