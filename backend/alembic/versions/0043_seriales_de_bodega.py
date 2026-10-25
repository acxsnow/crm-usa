"""Seriales de bodega (D-007 del plan de QA, `docs/pruebas QA JJ/01_REGISTRO_DEFECTOS.md`).

Un registro por unidad de los artículos «con serial»: en bodega, entregado a
una orden y su obra, o instalado. Así la casilla «Con serial» deja de ser una
promesa: la entrega pide el serial de cada unidad y «Equipos instalados» lo
cruza con lo que salió para la obra.

Revision ID: 0043
Revises: 0042
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def upgrade() -> None:
    op.create_table(
        "warehouse_serials",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("item_id", GUID(), sa.ForeignKey("warehouse_items.id"), nullable=False, index=True),
        sa.Column("serial", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_stock"),
        sa.Column("location_id", GUID(), sa.ForeignKey("warehouse_locations.id")),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), index=True),
        sa.Column("release_order_id", GUID(), sa.ForeignKey("warehouse_release_orders.id")),
        sa.Column("release_line_id", GUID(), sa.ForeignKey("warehouse_release_lines.id")),
        sa.Column("installed_equipment_id", GUID(), sa.ForeignKey("installed_equipment.id", ondelete="SET NULL"),
                  index=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("installed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("organization_id", "item_id", "serial", name="uq_warehouse_serial"),
    )
    op.create_index("ix_warehouse_serials_org_status", "warehouse_serials", ["organization_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_warehouse_serials_org_status", table_name="warehouse_serials")
    op.drop_table("warehouse_serials")
