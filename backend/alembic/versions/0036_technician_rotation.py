"""Rotación del técnico en la obra (plan bodega-cierre, fase 5).

El personal rota: con la obra iniciada, el administrador cambia el técnico con
la misma «Orden liberada» y el nuevo sigue donde el otro terminó.

- `project_technician_assignments`: quién fue el responsable y desde/hasta
  cuándo. El anterior sigue viendo la obra en solo lectura.
- `project_day_log_helpers`: los ayudantes de cada jornada (técnicos que fueron
  con el responsable). Ven la obra, no la llenan.

Cada obra con técnico arranca su historial con el responsable de hoy, desde la
fecha programada (o desde que se creó, si no la tiene).

Revision ID: 0036
Revises: 0035
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def upgrade() -> None:
    op.create_table(
        "project_technician_assignments", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("technician_user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date()),
        sa.Column("assigned_by_user_id", GUID(), sa.ForeignKey("users.id")),
    )
    op.create_table(
        "project_day_log_helpers", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("day_log_id", GUID(), sa.ForeignKey("project_day_logs.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.UniqueConstraint("day_log_id", "user_id", name="uq_day_log_helper"),
    )

    conn = op.get_bind()
    filas = conn.execute(sa.text(
        "SELECT id, organization_id, primary_technician_user_id, scheduled_date, created_at FROM projects"
        " WHERE primary_technician_user_id IS NOT NULL")).fetchall()
    tabla = sa.table("project_technician_assignments", sa.column("id", GUID()), sa.column("organization_id", GUID()),
                     sa.column("project_id", GUID()), sa.column("technician_user_id", GUID()),
                     sa.column("started_on", sa.Date()))
    if filas:
        op.bulk_insert(tabla, [{
            "id": uuid.uuid4(), "organization_id": f.organization_id, "project_id": f.id,
            "technician_user_id": f.primary_technician_user_id,
            "started_on": f.scheduled_date or f.created_at.date(),
        } for f in filas])


def downgrade() -> None:
    op.drop_table("project_day_log_helpers")
    op.drop_table("project_technician_assignments")
