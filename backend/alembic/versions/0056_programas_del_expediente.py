"""Varios programas por expediente (`case_programs`).

Una instalación puede ir a varios programas (TECH y GoZero, HEERA y GoZero),
cada uno con su aprobación y su pago; el formulario se llena una vez y una sola
firma vale para todos (cliente, 28 nov 2026). `cases.program_id` sigue siendo el
principal; la tabla guarda el principal y los adicionales con su decisión. Los
expedientes que ya tienen programa entran con él como principal y con la
decisión que diga su etapa. La firma guarda qué programas cubrió.

Revision ID: 0056
Revises: 0055
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.db.types import GUID

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APROBADAS = ("approved", "permit_in_progress", "ready_to_install", "installed", "inspection_pending",
             "billing_in_progress", "paid")


def upgrade() -> None:
    op.create_table(
        "case_programs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("case_id", GUID(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("program_id", GUID(), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approval_code", sa.String(100)),
        sa.Column("application_number", sa.String(100)),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by_user_id", GUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "program_id", name="uq_case_program"),
    )
    op.add_column("case_terms_acceptances", sa.Column("program_codes", sa.JSON()))

    bind = op.get_bind()
    filas = bind.execute(sa.text(
        "SELECT id, organization_id, program_id, stage_code, approval_code, application_number "
        "FROM cases WHERE program_id IS NOT NULL")).fetchall()
    if filas:
        tabla = sa.table("case_programs", sa.column("id", GUID()), sa.column("organization_id", GUID()),
                         sa.column("case_id", GUID()), sa.column("program_id", GUID()),
                         sa.column("is_primary", sa.Boolean()), sa.column("source", sa.String()),
                         sa.column("status", sa.String()), sa.column("approval_code", sa.String()),
                         sa.column("application_number", sa.String()))
        op.bulk_insert(tabla, [{
            "id": uuid.uuid4(), "organization_id": f.organization_id, "case_id": f.id, "program_id": f.program_id,
            "is_primary": True, "source": "manual",
            "status": "approved" if f.stage_code in APROBADAS else "rejected" if f.stage_code == "rejected"
            else "pending",
            "approval_code": f.approval_code, "application_number": f.application_number} for f in filas])


def downgrade() -> None:
    op.drop_column("case_terms_acceptances", "program_codes")
    op.drop_table("case_programs")
