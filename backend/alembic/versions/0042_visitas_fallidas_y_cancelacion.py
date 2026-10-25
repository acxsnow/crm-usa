"""Visitas fallidas, límite de reagendamiento y cancelación de la obra (D-001
del plan de QA, `docs/pruebas QA JJ/01_REGISTRO_DEFECTOS.md`).

Agrega a la obra el contador de visitas fallidas, los intentos extra que
autoriza Administración y los datos de la cancelación. Crea el registro de
cada visita fallida y la configuración de campo por organización (el límite).

Revision ID: 0042
Revises: 0041
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.add_column("projects", sa.Column("failed_visits_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("extra_visits_authorized", sa.Integer(), nullable=False,
                                        server_default="0"))
    op.add_column("projects", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.add_column("projects", sa.Column("cancelled_by_user_id", GUID()))
    op.add_column("projects", sa.Column("cancel_reason", sa.Text()))

    op.create_table(
        "project_visit_attempts", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("technician_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("recorded_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("scheduled_date", sa.Date()),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float()), sa.Column("longitude", sa.Float()),
    )
    op.create_table(
        "field_ops_settings", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("max_failed_visits", sa.Integer(), nullable=False, server_default="2"),
        sa.UniqueConstraint("organization_id", name="uq_field_ops_settings_org"),
    )


def downgrade() -> None:
    op.drop_table("field_ops_settings")
    op.drop_table("project_visit_attempts")
    for col in ("cancel_reason", "cancelled_by_user_id", "cancelled_at", "extra_visits_authorized",
                "failed_visits_count"):
        op.drop_column("projects", col)
