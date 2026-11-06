"""Pedidos del cliente del 4 nov 2026.

- La línea de cotización recuerda de qué artículo de bodega salió
  (`quote_lines.warehouse_item_id`); un material sin artículo queda por validar.
- Administración tiene los mismos permisos que Contabilidad. Solo se agregan los
  que le faltan; la bajada quita únicamente esos.
- El permiso «En trámite» (`in_process`) no cambia el esquema: el estado es texto.

Revision ID: 0051
Revises: 0050
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.db.types import GUID

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Los de Contabilidad que Administración no tenía al 4 nov 2026.
NUEVOS_ADMIN = [
    "accounting.read", "accounting.manage", "invoices.create", "invoices.update", "invoices.record_payment",
    "invoices.export", "dashboards.finance", "billing.configure", "expenses.read_all", "expenses.approve",
    "suppliers.manage", "payables.manage", "reconciliation.manage", "profitability.read", "accounting.export",
    "reports.generate", "reports.export", "notifications.read_own", "payroll.close", "bankfeeds.manage",
]


def upgrade() -> None:
    op.add_column("quote_lines", sa.Column("warehouse_item_id", GUID(),
                                           sa.ForeignKey("warehouse_items.id", ondelete="SET NULL")))
    conn = op.get_bind()
    for code in NUEVOS_ADMIN:
        conn.execute(sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r, permissions p"
            " WHERE r.code = 'admin_staff' AND p.code = :perm AND NOT EXISTS (SELECT 1 FROM role_permissions rp"
            "   WHERE rp.role_id = r.id AND rp.permission_id = p.id)").bindparams(perm=code))


def downgrade() -> None:
    conn = op.get_bind()
    for code in NUEVOS_ADMIN:
        conn.execute(sa.text(
            "DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE code = 'admin_staff')"
            " AND permission_id IN (SELECT id FROM permissions WHERE code = :perm)").bindparams(perm=code))
    op.drop_column("quote_lines", "warehouse_item_id")
