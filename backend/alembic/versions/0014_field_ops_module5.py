"""Módulo 5: checklist por programa, evidencias por categoría, permisos,
inspecciones, equipos instalados y materiales.

Spec: docs/superpowers/specs/2026-09-27-modulo-5-campo-design.md

- `evidence.category` deja de ser enum de Postgres y pasa a texto con catálogo
  en código (D5.4). Los valores viejos (before/during/after/damage/other) no
  existen en el catálogo del §7.1: pasan a la categoría genérica según el tipo
  de archivo. La base local y Render no tienen evidencias (ver 0013).

Revision ID: 0014
Revises: 0013
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_EVIDENCE_VALUES = ("before", "during", "after", "damage", "other")


def _org_project_columns() -> list:
    return [
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("organization_id", app.db.types.GUID(), nullable=False),
        sa.Column("project_id", app.db.types.GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _org_project_constraints(table: str) -> list:
    return [
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    ]


def _index_org_project(table: str) -> None:
    op.create_index(op.f(f"ix_{table}_organization_id"), table, ["organization_id"])
    op.create_index(op.f(f"ix_{table}_project_id"), table, ["project_id"])


def upgrade() -> None:
    # --- Checklist configurable -------------------------------------------
    op.add_column("checklist_templates", sa.Column("program_id", app.db.types.GUID(), nullable=True))
    op.create_foreign_key(
        "checklist_templates_program_id_fkey", "checklist_templates", "programs",
        ["program_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(op.f("ix_checklist_templates_program_id"), "checklist_templates", ["program_id"])

    for table in ("checklist_template_items", "project_checklist_items"):
        op.add_column(table, sa.Column("section", sa.String(120), nullable=True))
        op.add_column(table, sa.Column("evidence_category", sa.String(40), nullable=True))
        op.add_column(table, sa.Column("condition_code", sa.String(40), nullable=True))
        op.add_column(
            table,
            sa.Column("allows_not_applicable", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    op.add_column(
        "project_checklist_items",
        sa.Column("not_applicable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("project_checklist_items", sa.Column("not_applicable_reason", sa.Text(), nullable=True))

    op.add_column(
        "projects",
        sa.Column("installation_conditions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    # --- Evidencia: enum -> texto con catálogo ----------------------------
    # El default viejo es `'other'::evidence_category` y Postgres no cambia el
    # tipo de una columna cuyo default no puede convertir: se quita primero.
    op.alter_column("evidence", "category", server_default=None)
    op.alter_column(
        "evidence", "category",
        type_=sa.String(40), existing_nullable=False, postgresql_using="category::text",
    )
    op.alter_column("evidence", "category", server_default="additional_photo")
    op.execute(
        "UPDATE evidence SET category = CASE WHEN mime_type LIKE 'video/%' "
        "THEN 'additional_video' ELSE 'additional_photo' END "
        f"WHERE category IN {_OLD_EVIDENCE_VALUES}"
    )
    sa.Enum(name="evidence_category").drop(op.get_bind(), checkfirst=True)

    # --- Tablas nuevas ------------------------------------------------------
    op.create_table(
        "permits",
        *_org_project_columns(),
        sa.Column("permit_number", sa.String(100), nullable=True),
        sa.Column("jurisdiction", sa.String(150), nullable=False),
        sa.Column("permit_type", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("filed_on", sa.Date(), nullable=True),
        sa.Column("approved_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("not_required_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_org_project_constraints("permits"),
    )
    _index_org_project("permits")

    op.create_table(
        "inspections",
        *_org_project_columns(),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inspector_name", sa.String(255), nullable=True),
        sa.Column("result", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_by_user_id", app.db.types.GUID(), nullable=True),
        sa.Column("observations", sa.Text(), nullable=True),
        *_org_project_constraints("inspections"),
    )
    _index_org_project("inspections")

    op.create_table(
        "installed_equipment",
        *_org_project_columns(),
        sa.Column("equipment_type", sa.String(40), nullable=False),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_label", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", app.db.types.GUID(), nullable=True),
        *_org_project_constraints("installed_equipment"),
    )
    _index_org_project("installed_equipment")
    op.create_index(op.f("ix_installed_equipment_serial_number"), "installed_equipment", ["serial_number"])

    op.create_table(
        "project_materials",
        *_org_project_columns(),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit", sa.String(30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_org_project_constraints("project_materials"),
    )
    _index_org_project("project_materials")


def downgrade() -> None:
    op.drop_table("project_materials")
    op.drop_table("installed_equipment")
    op.drop_table("inspections")
    op.drop_table("permits")

    # Las 15 categorías no caben en el enum viejo: todo vuelve a "other".
    evidence_category = sa.Enum(*_OLD_EVIDENCE_VALUES, name="evidence_category")
    evidence_category.create(op.get_bind(), checkfirst=True)
    op.alter_column("evidence", "category", server_default=None)
    op.execute("UPDATE evidence SET category = 'other'")
    op.alter_column(
        "evidence", "category",
        type_=evidence_category, existing_nullable=False,
        postgresql_using="category::evidence_category", server_default="other",
    )

    op.drop_column("projects", "installation_conditions")
    op.drop_column("project_checklist_items", "not_applicable_reason")
    op.drop_column("project_checklist_items", "not_applicable")
    for table in ("project_checklist_items", "checklist_template_items"):
        op.drop_column(table, "allows_not_applicable")
        op.drop_column(table, "condition_code")
        op.drop_column(table, "evidence_category")
        op.drop_column(table, "section")

    op.drop_index(op.f("ix_checklist_templates_program_id"), table_name="checklist_templates")
    op.drop_constraint("checklist_templates_program_id_fkey", "checklist_templates", type_="foreignkey")
    op.drop_column("checklist_templates", "program_id")
