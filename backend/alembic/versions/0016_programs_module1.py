"""Módulo 1: programas, catálogo de campos, flujo versionado, T&C y zonas.

Spec `docs/superpowers/specs/2026-10-04-modulo-1-programas-design.md`.

- `programs` gana la identidad frente al cliente (funder, nombre, logo, texto
  de autorización, entidad que factura).
- `program_versions` gana estado (draft/published/archived), quién publicó,
  notas y los T&C que usa. Las versiones que ya existan quedan publicadas si
  tenían `published_at`.
- `program_zones` gana estado, ciudad, notas y activo.
- Tablas nuevas: `field_definitions`, `program_terms`, `workflow_phases`,
  `workflow_steps`, `workflow_step_fields`, `zone_assignments`.

Revision ID: 0016
Revises: 0015
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def _base(*, org=True):
    cols = [sa.Column("id", GUID(), nullable=False)]
    if org:
        cols.append(sa.Column("organization_id", GUID(), nullable=False))
    cols += [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]
    return cols


def _index(table, *cols):
    for col in cols:
        op.create_index(op.f(f"ix_{table}_{col}"), table, [col])


def upgrade() -> None:
    # --- programs: identidad frente al cliente --------------------------------
    for name, type_ in (("description", sa.Text()), ("funder_name", sa.String(255)),
                        ("customer_facing_name", sa.String(255)), ("logo_url", sa.String(1024)),
                        ("authorization_text", sa.Text()), ("invoice_entity", sa.String(255))):
        op.add_column("programs", sa.Column(name, type_, nullable=True))

    # --- program_zones -----------------------------------------------------------
    op.add_column("program_zones", sa.Column("state", sa.String(2)))
    op.add_column("program_zones", sa.Column("city", sa.String(120)))
    op.add_column("program_zones", sa.Column("notes", sa.Text()))
    op.add_column("program_zones", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))

    # --- catálogo y T&C ----------------------------------------------------------
    op.create_table(
        "field_definitions", *_base(),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("help_text", sa.Text()),
        sa.Column("field_type", sa.String(30), nullable=False),
        sa.Column("section", sa.String(120)),
        sa.Column("options", sa.JSON()),
        sa.Column("validation", sa.JSON()),
        sa.Column("binding", sa.String(60)),
        sa.Column("internal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_field_definition_key"),
    )
    _index("field_definitions", "organization_id")

    op.create_table(
        "program_terms", *_base(),
        sa.Column("program_id", GUID(), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="es"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "version", "language", name="uq_program_terms_version_lang"),
    )
    _index("program_terms", "organization_id", "program_id")

    # --- program_versions ----------------------------------------------------------
    op.add_column("program_versions", sa.Column("status", sa.String(20), nullable=False, server_default="draft"))
    op.add_column("program_versions", sa.Column("published_by_user_id", GUID()))
    op.add_column("program_versions", sa.Column("notes", sa.Text()))
    op.add_column("program_versions", sa.Column("terms_id", GUID()))
    op.create_foreign_key("fk_program_versions_terms", "program_versions", "program_terms", ["terms_id"], ["id"],
                          ondelete="SET NULL")
    op.execute("UPDATE program_versions SET status = 'published' WHERE published_at IS NOT NULL")

    # --- flujo ---------------------------------------------------------------------
    op.create_table(
        "workflow_phases", *_base(),
        sa.Column("version_id", GUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("role_code", sa.String(40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["version_id"], ["program_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("workflow_phases", "organization_id", "version_id")

    op.create_table(
        "workflow_steps", *_base(),
        sa.Column("phase_id", GUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["phase_id"], ["workflow_phases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("workflow_steps", "organization_id", "phase_id")

    op.create_table(
        "workflow_step_fields", *_base(),
        sa.Column("step_id", GUID(), nullable=False),
        sa.Column("field_id", GUID(), nullable=False),
        sa.Column("requirement", sa.String(20), nullable=False, server_default="optional"),
        sa.Column("condition", sa.JSON()),
        sa.Column("label_override", sa.String(255)),
        sa.Column("help_override", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["field_id"], ["field_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("step_id", "field_id", name="uq_workflow_step_field"),
    )
    _index("workflow_step_fields", "organization_id", "step_id", "field_id")

    # --- zonas ---------------------------------------------------------------------
    op.create_table(
        "zone_assignments", *_base(),
        sa.Column("zone_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["program_zones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zone_id", "user_id", name="uq_zone_assignment"),
    )
    _index("zone_assignments", "organization_id", "zone_id", "user_id")


def downgrade() -> None:
    op.drop_table("zone_assignments")
    op.drop_table("workflow_step_fields")
    op.drop_table("workflow_steps")
    op.drop_table("workflow_phases")
    op.drop_constraint("fk_program_versions_terms", "program_versions", type_="foreignkey")
    for col in ("terms_id", "notes", "published_by_user_id", "status"):
        op.drop_column("program_versions", col)
    op.drop_table("program_terms")
    op.drop_table("field_definitions")
    for col in ("active", "notes", "city", "state"):
        op.drop_column("program_zones", col)
    for col in ("invoice_entity", "authorization_text", "logo_url", "customer_facing_name", "funder_name",
                "description"):
        op.drop_column("programs", col)
