"""Estados y ciudades de referencia: `geo_states` y `geo_cities`.

Datos del sistema, no por organización. Los estados son los tres donde opera
Delta HVAC. Las ciudades salen del censo de EE. UU. (Gazetteer Files 2023,
«Places» de California, Arizona y Nevada): ciudades y pueblos incorporados y
comunidades no incorporadas (CDP), donde hay muchos parques de casas móviles.
Están en `alembic/data/us_cities.csv` (estado, nombre).

Sirven para validar el estado de una zona y sugerir la ciudad. Las direcciones
se siguen guardando como texto, así que esto no toca expedientes ni zonas.

Revision ID: 0024
Revises: 0023
"""
import csv
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATES = [
    ("CA", "California", "America/Los_Angeles", 0),
    ("AZ", "Arizona", "America/Phoenix", 1),
    ("NV", "Nevada", "America/Los_Angeles", 2),
]
_CITIES_CSV = Path(__file__).resolve().parents[1] / "data" / "us_cities.csv"


def upgrade() -> None:
    estados = op.create_table(
        "geo_states",
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("timezone", sa.String(60), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    ciudades = op.create_table(
        "geo_cities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("state_code", sa.String(2), sa.ForeignKey("geo_states.code"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.UniqueConstraint("state_code", "name", name="uq_geo_city_state_name"),
    )
    op.create_index("ix_geo_cities_state_code", "geo_cities", ["state_code"])

    op.bulk_insert(estados, [{"code": c, "name": n, "timezone": tz, "sort_order": o} for c, n, tz, o in _STATES])
    with _CITIES_CSV.open(encoding="utf-8") as f:
        op.bulk_insert(ciudades, [{"state_code": r["state"], "name": r["name"]} for r in csv.DictReader(f)])


def downgrade() -> None:
    op.drop_index("ix_geo_cities_state_code", table_name="geo_cities")
    op.drop_table("geo_cities")
    op.drop_table("geo_states")
