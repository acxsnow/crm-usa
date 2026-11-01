"""Contabilidad de doble partida: plan de cuentas, asientos y cierre contable.

Permisos `accounting.read` y `accounting.manage`. Spec
`2026-11-01-contabilidad-design.md`.

Revision ID: 0048
Revises: 0047
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(14, 2)
NEW_PERMISSIONS = {"accounting.read": "Ver la contabilidad y los estados financieros",
                   "accounting.manage": "Registrar asientos, editar el plan de cuentas y cerrar períodos"}
GRANTS = {"organization_admin": ["accounting.read", "accounting.manage"],
          "accounting": ["accounting.read", "accounting.manage"], "management": ["accounting.read"]}


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "accounting_accounts", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("code", sa.String(20), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False), sa.Column("system_key", sa.String(40)),
        sa.Column("tax_category", sa.String(80)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_accounting_account_code"),
        sa.UniqueConstraint("organization_id", "system_key", name="uq_accounting_account_system"),
    )
    op.create_table(
        "journal_entries", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("number", sa.String(30), nullable=False), sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.String(500), nullable=False), sa.Column("source_key", sa.String(80), index=True),
        sa.Column("source_date", sa.Date()), sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reversal_of_id", GUID(), sa.ForeignKey("journal_entries.id")),
        sa.Column("reversed_by_id", GUID(), sa.ForeignKey("journal_entries.id")),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")), sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("organization_id", "source_key", "revision", name="uq_journal_source_revision"),
        sa.UniqueConstraint("organization_id", "number", name="uq_journal_number"),
    )
    op.create_index("ix_journal_entries_org_date", "journal_entries", ["organization_id", "entry_date"])
    op.create_table(
        "journal_lines", sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("entry_id", GUID(), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("account_id", GUID(), sa.ForeignKey("accounting_accounts.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("debit", MONEY, nullable=False, server_default="0"), sa.Column("credit", MONEY, nullable=False, server_default="0"),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), index=True), sa.Column("memo", sa.String(255)),
    )
    op.create_index("ix_journal_lines_org_account", "journal_lines", ["organization_id", "account_id"])
    op.create_table(
        "accounting_settings", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("locked_through", sa.Date()), sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("organization_id", name="uq_accounting_settings_org"),
    )
    conn = op.get_bind()
    for code, description in NEW_PERMISSIONS.items():
        conn.execute(sa.text(
            "INSERT INTO permissions (id, code, description) SELECT gen_random_uuid(), :code, :description"
            " WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)").bindparams(code=code, description=description))
        conn.execute(sa.text(
            "INSERT INTO permission_module_items (id, module_id, permission_id, sort_order)"
            " SELECT gen_random_uuid(), m.id, p.id, 99 FROM permission_modules m, permissions p"
            " WHERE m.key = 'finance_close' AND p.code = :code AND NOT EXISTS (SELECT 1 FROM permission_module_items i"
            "   WHERE i.module_id = m.id AND i.permission_id = p.id)").bindparams(code=code))
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
    op.drop_table("accounting_settings")
    op.drop_index("ix_journal_lines_org_account", table_name="journal_lines")
    op.drop_table("journal_lines")
    op.drop_index("ix_journal_entries_org_date", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_table("accounting_accounts")
