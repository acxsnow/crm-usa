"""Presupuesto del proyecto y comparación contra lo real (punto 3 del cuestionario).

El supervisor estima antes de instalar: material, equipo, mano de obra, permisos
y otros. El presupuesto se puede armar a mano o copiando una lista predefinida
(punto 2), y nace en `borrador`; al aprobarlo se vuelve la referencia contra la
que se compara lo gastado.

Un proyecto puede tener varios presupuestos (se rehace, se corrige), pero solo
uno vigente: al aprobar uno nuevo, el anterior pasa a `reemplazado` en vez de
borrarse. Así el historial se conserva y la comparación nunca mira dos versiones
a la vez.

Categorías: `materials`, `equipment`, `labor`, `contractor`, `permit`, `services`
y `other` — los mismos códigos que el costo real de `finance`, para que la
desviación se pueda calcular por categoría sin traducir nada.

No crea permisos ni módulos: la 0027 ya dejó `budgets.manage` y
`budgets.approve`.

Revision ID: 0030
Revises: 0029
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID
MONEY = sa.Numeric(12, 2)
QUANTITY = sa.Numeric(10, 2)


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "project_budgets", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        # `borrador` → `aprobado`; el que se reemplaza queda en `reemplazado`.
        sa.Column("status", sa.String(20), nullable=False, server_default="borrador"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("approved_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_project_budgets_org_project", "project_budgets", ["organization_id", "project_id"])
    op.create_table(
        "project_budget_lines", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("budget_id", GUID(), sa.ForeignKey("project_budgets.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # La categoría del gasto (material, equipo, mano de obra, permiso, otro).
        sa.Column("category", sa.String(30), nullable=False, server_default="materials"),
        # Opcional: la mano de obra o un permiso no salen del catálogo de bodega.
        sa.Column("item_id", GUID(), sa.ForeignKey("warehouse_items.id"), index=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=False, server_default="unit"),
        sa.Column("unit_cost", MONEY, nullable=False, server_default="0"),
        # El monto se guarda: es lo que se aprobó y no se recalcula después.
        sa.Column("amount", MONEY, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_project_budget_lines_org_budget", "project_budget_lines",
                    ["organization_id", "budget_id"])


def downgrade() -> None:
    op.drop_index("ix_project_budget_lines_org_budget", table_name="project_budget_lines")
    op.drop_table("project_budget_lines")
    op.drop_index("ix_project_budgets_org_project", table_name="project_budgets")
    op.drop_table("project_budgets")
