"""Tarifas del cliente (1 nov): técnicos de planta a 45 USD la hora y 8 horas al
día, y el subcontratista del pedestal baja a 1.000 USD. Solo cambia las plantillas
que siguen con el valor inicial: las que alguien editó se respetan.

Revision ID: 0050
Revises: 0049
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LINEA = ("UPDATE cost_template_lines SET value = :nuevo WHERE category = 'contractor' AND value = :viejo"
          " AND description = 'Pago al contratista' AND template_id IN"
          " (SELECT id FROM cost_templates WHERE name = 'Pedestal (rebate) con subcontratista')")


def upgrade() -> None:
    op.add_column("attendance_settings", sa.Column("plant_hourly_rate", sa.Numeric(10, 2), nullable=False, server_default="45"))
    op.add_column("attendance_settings", sa.Column("plant_daily_hours", sa.Numeric(4, 2), nullable=False, server_default="8"))
    op.get_bind().execute(sa.text(_LINEA).bindparams(nuevo=1000, viejo=1050))


def downgrade() -> None:
    op.get_bind().execute(sa.text(_LINEA).bindparams(nuevo=1050, viejo=1000))
    op.drop_column("attendance_settings", "plant_daily_hours")
    op.drop_column("attendance_settings", "plant_hourly_rate")
