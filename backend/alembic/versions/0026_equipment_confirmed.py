"""«Guardar equipos instalados»: el proyecto registra cuándo y quién dio por
terminada la lista de equipos (spec 2026-10-18-guardar-equipos-y-avisos).

Los proyectos ya cerrados que tienen equipos quedan confirmados con la fecha de
la migración, para que su acta siga completa.

Revision ID: 0026
Revises: 0025
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("equipment_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("equipment_confirmed_by_user_id", app.db.types.GUID(), nullable=True))
    op.execute(
        "UPDATE projects SET equipment_confirmed_at = CURRENT_TIMESTAMP "
        "WHERE status = 'completed' AND EXISTS "
        "(SELECT 1 FROM installed_equipment e WHERE e.project_id = projects.id)"
    )


def downgrade() -> None:
    op.drop_column("projects", "equipment_confirmed_by_user_id")
    op.drop_column("projects", "equipment_confirmed_at")
