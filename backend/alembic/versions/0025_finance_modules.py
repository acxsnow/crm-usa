"""Gastos de campo, proveedores y cuentas por pagar, conciliación bancaria y
permiso `payables.approve` (spec 2026-10-13 de gastos, proveedores y finanzas).

Revision ID: 0025
Revises: 0024
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID
MONEY = sa.Numeric(12, 2)

_NEW_PERMISSIONS = {"payables.approve": "Aprobar y programar pagos a proveedores"}
_ROLE_GRANTS = {"organization_admin": ["payables.approve"], "management": ["payables.approve"]}


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "expenses", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), index=True),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False, server_default="own_money"),
        sa.Column("receipt_path", sa.String(500)), sa.Column("receipt_mime", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("reviewed_by_user_id", GUID()), sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_notes", sa.Text()), sa.Column("reimbursed_at", sa.Date()),
        sa.Column("reimbursement_reference", sa.String(120)),
    )
    op.create_index("ix_expenses_org_status", "expenses", ["organization_id", "status"])
    op.create_table(
        "suppliers", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(255), nullable=False), sa.Column("legal_name", sa.String(255)),
        sa.Column("tax_id", sa.String(40)), sa.Column("kinds", sa.JSON(), nullable=False),
        sa.Column("contact_name", sa.String(255)), sa.Column("phone", sa.String(40)),
        sa.Column("email", sa.String(255)), sa.Column("address", sa.String(500)),
        sa.Column("states", sa.JSON(), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("payment_method", sa.String(20)), sa.Column("bank_details", sa.Text()),
        sa.Column("license_number", sa.String(80)), sa.Column("license_expires_on", sa.Date()),
        sa.Column("insurance_expires_on", sa.Date()),
        sa.Column("w9_on_file", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "name", name="uq_supplier_name"),
    )
    op.create_table(
        "supplier_documents", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("supplier_id", GUID(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False), sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100)), sa.Column("original_filename", sa.String(255)),
        sa.Column("expires_on", sa.Date()), sa.Column("uploaded_by_user_id", GUID()),
    )
    op.create_table(
        "supplier_invoices", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("supplier_id", GUID(), sa.ForeignKey("suppliers.id"), nullable=False, index=True),
        sa.Column("number", sa.String(80), nullable=False), sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False), sa.Column("subtotal", MONEY, nullable=False),
        sa.Column("tax", MONEY, nullable=False, server_default="0"),
        sa.Column("shipping", MONEY, nullable=False, server_default="0"), sa.Column("total", MONEY, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_approval"),
        sa.Column("scheduled_payment_date", sa.Date()), sa.Column("notes", sa.Text()),
        sa.Column("file_path", sa.String(500)), sa.Column("file_mime", sa.String(100)),
        sa.Column("void_reason", sa.Text()), sa.Column("created_by_user_id", GUID()),
        sa.UniqueConstraint("organization_id", "supplier_id", "number", name="uq_supplier_invoice_number"),
    )
    op.create_index("ix_supplier_invoices_due", "supplier_invoices", ["organization_id", "status", "due_date"])
    op.create_table(
        "supplier_invoice_lines", sa.Column("id", GUID(), primary_key=True),
        sa.Column("invoice_id", GUID(), sa.ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="materials"),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit_cost", MONEY, nullable=False), sa.Column("amount", MONEY, nullable=False),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), index=True),
    )
    op.create_table(
        "supplier_invoice_approvals", sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("invoice_id", GUID(), sa.ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("capacity", sa.String(20), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False), sa.Column("notes", sa.String(500)),
        sa.UniqueConstraint("invoice_id", "user_id", name="uq_supplier_invoice_approval_user"),
    )
    op.create_table(
        "supplier_payments", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("supplier_id", GUID(), sa.ForeignKey("suppliers.id"), nullable=False, index=True),
        sa.Column("paid_on", sa.Date(), nullable=False), sa.Column("amount", MONEY, nullable=False),
        sa.Column("method", sa.String(20), nullable=False), sa.Column("reference", sa.String(120)),
        sa.Column("bank_account", sa.String(120)), sa.Column("notes", sa.Text()),
        sa.Column("file_path", sa.String(500)), sa.Column("file_mime", sa.String(100)),
        sa.Column("recorded_by_user_id", GUID()),
    )
    op.create_table(
        "supplier_payment_allocations", sa.Column("id", GUID(), primary_key=True),
        sa.Column("payment_id", GUID(), sa.ForeignKey("supplier_payments.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("invoice_id", GUID(), sa.ForeignKey("supplier_invoices.id"), nullable=False, index=True),
        sa.Column("amount", MONEY, nullable=False),
        sa.UniqueConstraint("payment_id", "invoice_id", name="uq_supplier_payment_invoice"),
    )
    op.create_table(
        "finance_settings", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("two_approval_threshold", MONEY, nullable=False, server_default="10000"),
        sa.Column("due_alert_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("document_alert_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_expense_amount", MONEY, nullable=False, server_default="5000"),
        sa.UniqueConstraint("organization_id", name="uq_finance_settings_org"),
    )
    op.create_table(
        "bank_statements", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("account_label", sa.String(120), nullable=False), sa.Column("original_filename", sa.String(255)),
        sa.Column("period_start", sa.Date()), sa.Column("period_end", sa.Date()),
        sa.Column("imported_by_user_id", GUID()),
    )
    op.create_table(
        "bank_statement_lines", sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("statement_id", GUID(), sa.ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("line_date", sa.Date(), nullable=False), sa.Column("description", sa.String(500), nullable=False),
        sa.Column("reference", sa.String(120)), sa.Column("amount", MONEY, nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="unmatched"),
        sa.Column("matched_type", sa.String(30)), sa.Column("matched_id", GUID()),
        sa.Column("matched_by_user_id", GUID()), sa.Column("matched_at", sa.DateTime(timezone=True)),
        sa.Column("auto_matched", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(500)),
    )
    op.create_index("ix_bank_lines_status", "bank_statement_lines", ["organization_id", "status"])

    for code, description in _NEW_PERMISSIONS.items():
        op.execute(sa.text(
            "INSERT INTO permissions (id, code, description) SELECT gen_random_uuid(), :code, :description "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
        ).bindparams(code=code, description=description))
    for role_code, codes in _ROLE_GRANTS.items():
        for code in codes:
            op.execute(sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p WHERE r.code = :role AND p.code = :perm "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ).bindparams(role=role_code, perm=code))
    for code in _NEW_PERMISSIONS:
        op.execute(sa.text(
            "INSERT INTO permission_module_items (id, module_id, permission_id, sort_order) "
            "SELECT gen_random_uuid(), m.id, p.id, 100 FROM permission_modules m, permissions p "
            "WHERE m.key = 'payables' AND p.code = :perm "
            "AND NOT EXISTS (SELECT 1 FROM permission_module_items i WHERE i.module_id = m.id AND i.permission_id = p.id)"
        ).bindparams(perm=code))


def downgrade() -> None:
    for code in _NEW_PERMISSIONS:
        op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
    op.drop_index("ix_bank_lines_status", table_name="bank_statement_lines")
    for t in ("bank_statement_lines", "bank_statements", "finance_settings", "supplier_payment_allocations",
              "supplier_payments", "supplier_invoice_approvals", "supplier_invoice_lines"):
        op.drop_table(t)
    op.drop_index("ix_supplier_invoices_due", table_name="supplier_invoices")
    for t in ("supplier_invoices", "supplier_documents", "suppliers"):
        op.drop_table(t)
    op.drop_index("ix_expenses_org_status", table_name="expenses")
    op.drop_table("expenses")
