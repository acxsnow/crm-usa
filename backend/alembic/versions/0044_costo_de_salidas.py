"""Costo unitario en las salidas de bodega que no lo guardaron (D-018 del plan de QA).

La entrega de una orden de salida registraba el movimiento sin `unit_cost`, y
el costo de la obra se calculaba con el costo vigente del catálogo: al editarlo
cambiaba el costo de obras ya cerradas. Desde ahora la entrega guarda el costo
del día; las salidas anteriores se completan con el costo actual del catálogo,
que es el mejor dato disponible.

Revision ID: 0044
Revises: 0043
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE warehouse_movements SET unit_cost = (SELECT i.unit_cost FROM warehouse_items i "
        "WHERE i.id = warehouse_movements.item_id) "
        "WHERE movement_type = 'salida' AND unit_cost IS NULL"
    )


def downgrade() -> None:
    # No se puede saber cuáles se completaron aquí: el costo queda guardado.
    pass
