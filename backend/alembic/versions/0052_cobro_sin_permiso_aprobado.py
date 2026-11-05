"""Respuestas del cliente del 5 nov 2026: el cobro se radica con el permiso en
cualquier estado. Se apaga el requisito «Permiso municipal aprobado» en los
programas que ya existen (quien lo necesite lo vuelve a encender en la
configuración del programa). Cerrar el expediente sí exige el aprobado; eso es
una guarda en código, no un dato.

Revision ID: 0052
Revises: 0051
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE program_claim_requirements SET active = false WHERE code = 'permit_approved'"))


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE program_claim_requirements SET active = true WHERE code = 'permit_approved'"))
