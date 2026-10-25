"""Pagos en línea (Stripe) y banca conectada (Plaid). Spec
`2026-10-25-pagos-tarjeta-design.md`.

Crea los enlaces de pago, el registro de eventos ya procesados, los bancos,
cuentas y movimientos conectados y las reglas bancarias. Agrega a los pagos de
factura el proveedor, la referencia externa y la comisión. Suma dos permisos a
los módulos de facturación y de conciliación, y los concede solo donde falten.

Revision ID: 0041
Revises: 0040
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID
MONEY = sa.Numeric(12, 2)

NEW_PERMISSIONS = {
    "payments.collect": ("Cobrar facturas en línea: enlace de pago, QR y anticipos", "projects"),
    "bankfeeds.manage": ("Conectar bancos y tarjetas, revisar y clasificar sus movimientos", "finance_close"),
}
GRANTS = {
    "organization_admin": ["payments.collect", "bankfeeds.manage"],
    "admin_staff": ["payments.collect"],
    "field_technician": ["payments.collect"],
    "accounting": ["payments.collect", "bankfeeds.manage"],
}


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.add_column("invoice_payments", sa.Column("provider", sa.String(20)))
    op.add_column("invoice_payments", sa.Column("external_id", sa.String(255)))
    op.add_column("invoice_payments", sa.Column("fee_amount", MONEY))
    op.create_index("ix_invoice_payments_external_id", "invoice_payments", ["external_id"])

    op.create_table(
        "payment_links", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("invoice_id", GUID(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="full"),
        sa.Column("amount", MONEY),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("sent_to_email", sa.String(255)), sa.Column("sent_to_phone", sa.String(32)),
        sa.Column("last_sent_at", sa.DateTime(timezone=True)), sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)), sa.Column("stripe_session_id", sa.String(255)),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
    )
    op.create_table(
        "provider_events", sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("provider", sa.String(20), nullable=False), sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False), sa.Column("summary", sa.JSON()),
        sa.UniqueConstraint("provider", "event_id", name="uq_provider_event"),
    )
    op.create_table(
        "bank_connections", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("institution_name", sa.String(255), nullable=False), sa.Column("institution_id", sa.String(80)),
        sa.Column("plaid_item_id", sa.String(255), nullable=False, index=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False), sa.Column("sync_cursor", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)), sa.Column("last_error", sa.String(500)),
        sa.Column("connected_by_user_id", GUID(), sa.ForeignKey("users.id")),
    )
    op.create_table(
        "bank_accounts", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("connection_id", GUID(), sa.ForeignKey("bank_connections.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("plaid_account_id", sa.String(255), nullable=False), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mask", sa.String(10)), sa.Column("type", sa.String(30)), sa.Column("subtype", sa.String(40)),
        sa.Column("current_balance", MONEY), sa.Column("available_balance", MONEY), sa.Column("currency", sa.String(3)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "plaid_account_id", name="uq_bank_account_plaid"),
    )
    op.create_table(
        "bank_rules", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("contains", sa.String(120), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False, server_default="out"),
        sa.Column("amount_min", MONEY), sa.Column("amount_max", MONEY),
        sa.Column("account_id", GUID(), sa.ForeignKey("bank_accounts.id", ondelete="CASCADE")),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id")),
        sa.Column("auto_add", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("memo", sa.Text()),
    )
    op.create_table(
        "bank_transactions", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("account_id", GUID(), sa.ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("plaid_transaction_id", sa.String(255), nullable=False),
        sa.Column("posted_date", sa.Date(), nullable=False), sa.Column("amount", MONEY, nullable=False),
        sa.Column("description", sa.String(500), nullable=False), sa.Column("merchant_name", sa.String(255)),
        sa.Column("plaid_category", sa.String(120)),
        sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="review"),
        sa.Column("suggested_category", sa.String(30)),
        sa.Column("suggested_project_id", GUID(), sa.ForeignKey("projects.id")),
        sa.Column("suggested_rule_id", GUID(), sa.ForeignKey("bank_rules.id", ondelete="SET NULL")),
        sa.Column("expense_id", GUID(), sa.ForeignKey("expenses.id", ondelete="SET NULL")),
        sa.Column("matched_type", sa.String(30)), sa.Column("matched_id", GUID()),
        sa.Column("category", sa.String(30)), sa.Column("project_id", GUID(), sa.ForeignKey("projects.id")),
        sa.Column("memo", sa.String(500)),
        sa.Column("reviewed_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "plaid_transaction_id", name="uq_bank_transaction_plaid"),
    )
    op.create_index("ix_bank_transactions_org_status_date", "bank_transactions",
                    ["organization_id", "review_status", "posted_date"])

    conn = op.get_bind()
    for code, (description, module_key) in NEW_PERMISSIONS.items():
        conn.execute(sa.text(
            "INSERT INTO permissions (id, code, description) SELECT gen_random_uuid(), :code, :description"
            " WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)").bindparams(code=code, description=description))
        conn.execute(sa.text(
            "INSERT INTO permission_module_items (id, module_id, permission_id, sort_order)"
            " SELECT gen_random_uuid(), m.id, p.id, 99 FROM permission_modules m, permissions p"
            " WHERE m.key = :key AND p.code = :code AND NOT EXISTS (SELECT 1 FROM permission_module_items i"
            "   WHERE i.module_id = m.id AND i.permission_id = p.id)").bindparams(key=module_key, code=code))
    for role, codes in GRANTS.items():
        for code in codes:
            conn.execute(sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r, permissions p"
                " WHERE r.code = :role AND p.code = :perm AND NOT EXISTS (SELECT 1 FROM role_permissions rp"
                "   WHERE rp.role_id = r.id AND rp.permission_id = p.id)").bindparams(role=role, perm=code))


def downgrade() -> None:
    conn = op.get_bind()
    for code in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permission_module_items WHERE permission_id IN"
                             " (SELECT id FROM permissions WHERE code = :code)").bindparams(code=code))
        conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN"
                             " (SELECT id FROM permissions WHERE code = :code)").bindparams(code=code))
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
    op.drop_index("ix_bank_transactions_org_status_date", table_name="bank_transactions")
    for tabla in ("bank_transactions", "bank_rules", "bank_accounts", "bank_connections", "provider_events",
                  "payment_links"):
        op.drop_table(tabla)
    op.drop_index("ix_invoice_payments_external_id", table_name="invoice_payments")
    for col in ("fee_amount", "external_id", "provider"):
        op.drop_column("invoice_payments", col)
