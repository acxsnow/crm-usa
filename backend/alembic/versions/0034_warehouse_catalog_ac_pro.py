"""Catálogo de bodega listo para AC Pro (plan bodega-cierre, fase 3).

- `warehouse_categories`: las categorías dejan de estar fijas en el código y
  cada organización las administra (la hoja «Listas» del cuestionario decía que
  el cliente podía cambiarlas o agregar las suyas). El artículo sigue guardando
  el código, así que los artículos que ya existen no cambian.
- `warehouse_items` gana `brand` y `manufacturer_part`: AC Pro identifica cada
  producto con su código (que va en `sku`), el número del fabricante y la marca.

Las categorías no se siembran aquí: se crean la primera vez que la organización
las usa, igual que las plantillas de costo (0033), y así también las tienen las
organizaciones nuevas.

Revision ID: 0034
Revises: 0033
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def upgrade() -> None:
    op.create_table(
        "warehouse_categories",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("organization_id", "code", name="uq_warehouse_category_code"),
        sa.UniqueConstraint("organization_id", "label", name="uq_warehouse_category_label"),
    )
    op.add_column("warehouse_items", sa.Column("brand", sa.String(120)))
    op.add_column("warehouse_items", sa.Column("manufacturer_part", sa.String(80)))


def downgrade() -> None:
    op.drop_column("warehouse_items", "manufacturer_part")
    op.drop_column("warehouse_items", "brand")
    op.drop_table("warehouse_categories")
