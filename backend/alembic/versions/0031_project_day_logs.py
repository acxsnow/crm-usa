"""Diario de obra: la jornada día por día (punto 4 del cuestionario).

Los trabajos fuera de rebate duran varios días y no siempre con el mismo
técnico. El diario guarda, por obra y por día, quién estuvo, cuántas horas, qué
se hizo, hasta dónde se avanzó, qué material faltó, qué hay que llevar al día
siguiente y qué incidencias hubo.

El técnico vive en la **jornada**, no en el proyecto: por eso la misma obra
puede tener un técnico distinto cada día. Una obra con más de una jornada es
una obra «de varios días», y eso es lo que la Agenda marca.

Dos decisiones del modelo:

- `project_day_log_materials` puede o no mover existencia. Con artículo y
  ubicación, la línea descuenta la camioneta y el material se convierte en
  costo de la obra (como cualquier otra salida); sin ellos, es solo la
  anotación del día (material comprado directo a la obra). `movement_id` deja
  el rastro del movimiento que la descontó.
- Los gastos del día **no** se guardan acá: se leen de `expenses` por fecha,
  que es donde ya están capturados.

La restricción `uq_project_day_log_date` deja una sola jornada por día y obra:
el diario se lee como una línea por día.

No crea permisos ni módulos: la 0027 ya dejó `daylogs.manage`.

Revision ID: 0031
Revises: 0030
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID
QUANTITY = sa.Numeric(10, 2)


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "project_day_logs", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("log_date", sa.Date(), nullable=False),
        # El técnico del día, que no tiene por qué ser el asignado al proyecto.
        sa.Column("technician_user_id", GUID(), sa.ForeignKey("users.id"), index=True),
        # Con quién más estuvo (cuadrilla). Texto libre: no siempre son usuarios.
        sa.Column("crew", sa.String(255)),
        sa.Column("hours", QUANTITY),
        sa.Column("work_done", sa.Text()),
        sa.Column("progress_note", sa.String(255)),
        sa.Column("missing_materials", sa.Text()),
        sa.Column("next_day_plan", sa.Text()),
        sa.Column("incidents", sa.Text()),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("updated_by_user_id", GUID(), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_project_day_logs_org_project", "project_day_logs", ["organization_id", "project_id"])
    # Una jornada por día y obra: el diario es una línea por día.
    op.create_unique_constraint("uq_project_day_log_date", "project_day_logs",
                                ["organization_id", "project_id", "log_date"])

    op.create_table(
        "project_day_log_materials", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("day_log_id", GUID(), sa.ForeignKey("project_day_logs.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # Opcional: el material de la obra que no está en el catálogo va a mano.
        sa.Column("item_id", GUID(), sa.ForeignKey("warehouse_items.id"), index=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=False, server_default="unit"),
        # De dónde salió (la camioneta). Nulo = la línea no movió existencia.
        sa.Column("location_id", GUID(), sa.ForeignKey("warehouse_locations.id")),
        # El movimiento que descontó la existencia.
        sa.Column("movement_id", GUID(), sa.ForeignKey("warehouse_movements.id")),
        sa.Column("notes", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_project_day_log_materials_org_log", "project_day_log_materials",
                    ["organization_id", "day_log_id"])


def downgrade() -> None:
    op.drop_index("ix_project_day_log_materials_org_log", table_name="project_day_log_materials")
    op.drop_table("project_day_log_materials")
    op.drop_constraint("uq_project_day_log_date", "project_day_logs", type_="unique")
    op.drop_index("ix_project_day_logs_org_project", table_name="project_day_logs")
    op.drop_table("project_day_logs")
