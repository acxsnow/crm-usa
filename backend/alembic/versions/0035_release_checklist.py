"""La lista predefinida como checklist de la salida (plan bodega-cierre, fase 2).

El dueño pidió «algo preestablecido que el técnico use como checklist para que no
se le olviden cosas que sí o sí debe llevar». Al aplicar la lista, la salida ya
copiaba artículo, cantidad y calibre; ahora copia también la sección y si es
obligatorio, y el técnico marca «lo llevo» al cargar la camioneta:

- `warehouse_release_lines`: `section`, `is_required`, `loaded_at` y
  `loaded_by_user_id`.
- `warehouse_release_orders.omissions`: los obligatorios que se quitaron al armar
  la orden, con el motivo, para que quien autoriza lo vea.

Revision ID: 0035
Revises: 0034
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def upgrade() -> None:
    op.add_column("warehouse_release_lines", sa.Column("section", sa.String(120)))
    op.add_column("warehouse_release_lines",
                  sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("warehouse_release_lines", sa.Column("loaded_at", sa.DateTime(timezone=True)))
    op.add_column("warehouse_release_lines",
                  sa.Column("loaded_by_user_id", GUID(), sa.ForeignKey("users.id")))
    op.add_column("warehouse_release_orders",
                  sa.Column("omissions", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("warehouse_release_orders", "omissions")
    op.drop_column("warehouse_release_lines", "loaded_by_user_id")
    op.drop_column("warehouse_release_lines", "loaded_at")
    op.drop_column("warehouse_release_lines", "is_required")
    op.drop_column("warehouse_release_lines", "section")
