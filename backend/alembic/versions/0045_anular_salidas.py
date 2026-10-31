"""Anular una salida de bodega que todavía no se entregó.

Quien la pidió (o bodega) la anula con motivo mientras no se haya entregado:
nada salió de bodega, así que no hay movimientos que deshacer. Antes la única
salida era que otra persona la rechazara.

Revision ID: 0045
Revises: 0044
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("warehouse_release_orders",
                  sa.Column("cancelled_by_user_id", GUID(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("warehouse_release_orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("warehouse_release_orders", sa.Column("cancel_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("warehouse_release_orders", "cancel_reason")
    op.drop_column("warehouse_release_orders", "cancelled_at")
    op.drop_column("warehouse_release_orders", "cancelled_by_user_id")
