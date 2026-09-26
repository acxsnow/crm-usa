"""Saca `programs.read` del módulo `config`

Un módulo se abre con **cualquiera** de sus permisos
(`modules_for_permissions`). `programs.read` estaba a la vez en `cases` y en
`config`, así que al vendedor —que lo tiene para elegir el programa desde el
expediente— se le encendía el módulo de configuración entero y veía
"Configuración de programas" en el menú.

Leer el catálogo de programas es parte de trabajar un expediente; administrar
un programa es otra cosa y la cubre `programs.manage`, que sigue viviendo solo
en `config`. Nadie pierde acceso: quien administra programas conserva
`programs.manage`.

Corrige las filas de **todas** las organizaciones y también la plantilla del
sistema (`organization_id` nulo), porque cada organización tiene su copia
editable.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ITEM = sa.text(
    """
    SELECT pmi.id
      FROM permission_module_items pmi
      JOIN permission_modules pm ON pm.id = pmi.module_id
      JOIN permissions p ON p.id = pmi.permission_id
     WHERE pm.key = 'config' AND p.code = 'programs.read'
    """
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM permission_module_items
             WHERE id IN (
                SELECT pmi.id
                  FROM permission_module_items pmi
                  JOIN permission_modules pm ON pm.id = pmi.module_id
                  JOIN permissions p ON p.id = pmi.permission_id
                 WHERE pm.key = 'config' AND p.code = 'programs.read'
             )
            """
        )
    )


def downgrade() -> None:
    """Vuelve a meter `programs.read` en cada `config` que no lo tenga.

    `ON CONFLICT DO NOTHING` cubre la organización que ya lo hubiera agregado a
    mano después de la subida."""
    op.execute(
        sa.text(
            """
            INSERT INTO permission_module_items (id, module_id, permission_id, sort_order)
            SELECT gen_random_uuid(), pm.id, p.id, 0
              FROM permission_modules pm
              CROSS JOIN permissions p
             WHERE pm.key = 'config' AND p.code = 'programs.read'
            ON CONFLICT (module_id, permission_id) DO NOTHING
            """
        )
    )
