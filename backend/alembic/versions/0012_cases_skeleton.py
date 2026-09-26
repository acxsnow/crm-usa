"""Esqueleto del expediente (Case)

Crea la entidad central del flujo operativo de Delta HVAC y las tablas mínimas
de programa de las que depende. Es la base sobre la que arranca la Cadena B
(módulos 4, 5 y 6): ver `docs/contratos/case.md` y
`docs/superpowers/specs/2026-09-25-esqueleto-case-design.md`.

Qué crea:

- `programs`, `program_versions`, `program_zones` — mínimas; las llena el
  módulo 1. Las dos últimas nacen vacías, pero existen desde ahora porque
  `Case` guarda con qué versión y zona nació y ese dato no se reconstruye.
- `cases` — el expediente. `customer_id` nullable a propósito: el expediente es
  la puerta, y el cliente aparece solo si abren.
- `case_stage_events` — el historial inmutable del que salen todos los reportes
  de tiempos del PDF §7.
- `projects.case_id` — la columna con la que Mateo engancha su módulo 5.
  `projects.opportunity_id` se conserva hasta que se retire `Opportunity`.

**No borra nada.** El retiro de `Opportunity`, `Lead` y `applications` es
posterior y va en el módulo 1.

Nota: el autogenerador propone además quitar las llaves foráneas de
`organization_id` de casi todas las tablas, porque `OrgScopedMixin` no las
declara aunque la migración `0001` sí las creó. Eso es una diferencia
preexistente entre el modelo y la base, ajena a este cambio, y se dejó fuera a
propósito: no se arregla deuda de otro sitio dentro de una migración de
funcionalidad.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('programs',
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('is_system_template', sa.Boolean(), nullable=False),
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('organization_id', app.db.types.GUID(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'code', name='uq_program_org_code')
    )
    op.create_index(op.f('ix_programs_organization_id'), 'programs', ['organization_id'], unique=False)
    op.create_table('program_versions',
    sa.Column('program_id', app.db.types.GUID(), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('organization_id', app.db.types.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('program_id', 'version', name='uq_program_version')
    )
    op.create_index(op.f('ix_program_versions_organization_id'), 'program_versions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_program_versions_program_id'), 'program_versions', ['program_id'], unique=False)
    op.create_table('program_zones',
    sa.Column('program_id', app.db.types.GUID(), nullable=True),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('organization_id', app.db.types.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'code', name='uq_program_zone_org_code')
    )
    op.create_index(op.f('ix_program_zones_organization_id'), 'program_zones', ['organization_id'], unique=False)
    op.create_index(op.f('ix_program_zones_program_id'), 'program_zones', ['program_id'], unique=False)
    op.create_table('cases',
    sa.Column('case_number', sa.String(length=30), nullable=False),
    sa.Column('source', sa.String(length=20), server_default='visit', nullable=False),
    sa.Column('program_id', app.db.types.GUID(), nullable=True),
    sa.Column('program_version_id', app.db.types.GUID(), nullable=True),
    sa.Column('zone_id', app.db.types.GUID(), nullable=True),
    sa.Column('customer_id', app.db.types.GUID(), nullable=True),
    sa.Column('assigned_salesperson_id', app.db.types.GUID(), nullable=True),
    sa.Column('assigned_admin_id', app.db.types.GUID(), nullable=True),
    sa.Column('normalized_address', sa.String(length=500), nullable=True),
    sa.Column('stage_code', sa.String(length=40), nullable=False),
    sa.Column('substatus_code', sa.String(length=40), nullable=True),
    sa.Column('stage_reason', sa.Text(), nullable=True),
    sa.Column('application_number', sa.String(length=100), nullable=True),
    sa.Column('approval_code', sa.String(length=100), nullable=True),
    sa.Column('funder_status_code', sa.String(length=50), nullable=True),
    sa.Column('first_contact_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('scheduled_install_date', sa.Date(), nullable=True),
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('organization_id', app.db.types.GUID(), nullable=False),
    sa.Column('address_street', sa.String(length=255), nullable=True),
    sa.Column('address_unit', sa.String(length=50), nullable=True),
    sa.Column('address_city', sa.String(length=120), nullable=True),
    sa.Column('address_state', sa.String(length=2), nullable=True),
    sa.Column('address_zip', sa.String(length=10), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['program_version_id'], ['program_versions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['zone_id'], ['program_zones.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'case_number', name='uq_case_org_number')
    )
    op.create_index('ix_case_org_property', 'cases', ['organization_id', 'normalized_address', 'address_unit'], unique=False)
    op.create_index('ix_case_org_stage', 'cases', ['organization_id', 'stage_code'], unique=False)
    op.create_index(op.f('ix_cases_assigned_admin_id'), 'cases', ['assigned_admin_id'], unique=False)
    op.create_index(op.f('ix_cases_assigned_salesperson_id'), 'cases', ['assigned_salesperson_id'], unique=False)
    op.create_index(op.f('ix_cases_customer_id'), 'cases', ['customer_id'], unique=False)
    op.create_index(op.f('ix_cases_funder_status_code'), 'cases', ['funder_status_code'], unique=False)
    op.create_index(op.f('ix_cases_normalized_address'), 'cases', ['normalized_address'], unique=False)
    op.create_index(op.f('ix_cases_organization_id'), 'cases', ['organization_id'], unique=False)
    op.create_index(op.f('ix_cases_program_id'), 'cases', ['program_id'], unique=False)
    op.create_index(op.f('ix_cases_program_version_id'), 'cases', ['program_version_id'], unique=False)
    op.create_index(op.f('ix_cases_stage_code'), 'cases', ['stage_code'], unique=False)
    op.create_index(op.f('ix_cases_zone_id'), 'cases', ['zone_id'], unique=False)
    op.create_table('case_stage_events',
    sa.Column('case_id', app.db.types.GUID(), nullable=False),
    sa.Column('from_stage_code', sa.String(length=40), nullable=True),
    sa.Column('to_stage_code', sa.String(length=40), nullable=False),
    sa.Column('from_substatus_code', sa.String(length=40), nullable=True),
    sa.Column('to_substatus_code', sa.String(length=40), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('actor_user_id', app.db.types.GUID(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', app.db.types.GUID(), nullable=False),
    sa.Column('organization_id', app.db.types.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_case_stage_event_case_time', 'case_stage_events', ['case_id', 'occurred_at'], unique=False)
    op.create_index(op.f('ix_case_stage_events_actor_user_id'), 'case_stage_events', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_case_stage_events_case_id'), 'case_stage_events', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_stage_events_organization_id'), 'case_stage_events', ['organization_id'], unique=False)
    # ### end Alembic commands ###


    # La columna con la que la Cadena B engancha el proyecto al expediente.
    op.add_column("projects", sa.Column("case_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_projects_case_id"), "projects", ["case_id"], unique=False)
    op.create_foreign_key("projects_case_id_fkey", "projects", "cases", ["case_id"], ["id"])

def downgrade() -> None:
    op.drop_constraint("projects_case_id_fkey", "projects", type_="foreignkey")
    op.drop_index(op.f("ix_projects_case_id"), table_name="projects")
    op.drop_column("projects", "case_id")
    op.drop_table("case_stage_events")
    op.drop_table("cases")
    op.drop_table("program_zones")
    op.drop_table("program_versions")
    op.drop_table("programs")
