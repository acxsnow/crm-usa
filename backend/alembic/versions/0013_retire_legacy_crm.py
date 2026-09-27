"""Retira el modelo del CRM anterior

Cierra el hallazgo COD-01 de la auditoría del 25 de septiembre: convivían dos
formas de representar lo mismo y ninguna regla impedía usar la equivocada.

Qué se retira y por qué:

- `leads` — el expediente cubre la puerta desde el primer toque, así que un
  prospecto y un expediente eran la misma cosa con dos nombres.
- `opportunities` — reemplazada por `cases`. `projects.opportunity_id` se va con
  ella: el proyecto ahora nace del expediente al aprobarse
  (`field_ops/case_hooks.py`).
- `quotes` y `quote_line_items` — el flujo del PDF no cotiza; nunca se usaron.
- `pipeline_stages` — las etapas viven en `cases/stages.py`, en código, con sus
  transiciones validadas.

Los permisos `leads.manage`, `opportunities.manage` y `quotes.manage` se borran
del catálogo; el borrado en cascada limpia su asignación a roles y su
pertenencia a módulos.

**Lo que NO se retira:** `applications` y `application_documents`. Son la única
pantalla de expedientes que funciona hoy, y se borran al terminar el módulo 2,
cuando sus datos vivan en `step_submissions`.

Todas las tablas estaban vacías al aplicar esta migración. El `downgrade()`
recrea la estructura, no los datos: no había ninguno que perder.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = ("leads.manage", "opportunities.manage", "quotes.manage")


def upgrade() -> None:
    op.drop_constraint("projects_opportunity_id_fkey", "projects", type_="foreignkey")
    op.drop_index("ix_projects_opportunity_id", table_name="projects")
    op.drop_column("projects", "opportunity_id")

    # `applications.lead_id` apuntaba a `leads`. Sin prospectos la columna no
    # significa nada, y la llave foránea impide borrar la tabla.
    # El índice nunca llegó a crearse en la base; solo existe la llave foránea.
    op.drop_constraint("applications_lead_id_fkey", "applications", type_="foreignkey")
    op.drop_column("applications", "lead_id")

    op.drop_table("quote_line_items")
    op.drop_table("quotes")
    op.drop_table("opportunities")
    op.drop_table("leads")
    op.drop_table("pipeline_stages")

    op.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", _PERMISOS, expanding=True)
        )
    )


def downgrade() -> None:
    """Recrea la estructura mínima. No restaura datos: no había."""
    op.create_table(
        "pipeline_stages",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("organization_id", app.db.types.GUID(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_won", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_lost", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "leads",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("organization_id", app.db.types.GUID(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "opportunities",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("organization_id", app.db.types.GUID(), nullable=False),
        sa.Column("customer_id", app.db.types.GUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("stage_id", app.db.types.GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "quotes",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("organization_id", app.db.types.GUID(), nullable=False),
        sa.Column("customer_id", app.db.types.GUID(), nullable=False),
        sa.Column("quote_number", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "quote_line_items",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("quote_id", app.db.types.GUID(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("applications", sa.Column("lead_id", app.db.types.GUID(), nullable=True))
    op.create_foreign_key(
        "applications_lead_id_fkey", "applications", "leads", ["lead_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("projects", sa.Column("opportunity_id", app.db.types.GUID(), nullable=True))
    op.create_index("ix_projects_opportunity_id", "projects", ["opportunity_id"])
    op.create_foreign_key(
        "projects_opportunity_id_fkey", "projects", "opportunities", ["opportunity_id"], ["id"]
    )
