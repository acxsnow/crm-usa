"""Varios programas por expediente (`case_programs`).

Una instalación puede ir a varios programas (TECH y GoZero, HEERA y GoZero),
cada uno con su solicitud y su pago. `cases.program_id` sigue siendo el
principal; la tabla guarda el principal y los adicionales. Los expedientes que
ya tienen programa entran con él como principal.

Revision ID: 0056
Revises: 0055
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.db.types import GUID

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "program_id", name="uq_case_program"),
    )
    # Los expedientes que ya tienen programa: ese es su principal.
    bind = op.get_bind()
    filas = bind.execute(sa.text(
        "SELECT id, organization_id, program_id FROM cases WHERE program_id IS NOT NULL")).fetchall()
    if filas:
        import uuid

        tabla = sa.table("case_programs", sa.column("id", GUID()), sa.column("organization_id", GUID()),
                         sa.column("case_id", GUID()), sa.column("program_id", GUID()),
                         sa.column("is_primary", sa.Boolean()), sa.column("source", sa.String()))
        op.bulk_insert(tabla, [{"id": uuid.uuid4(), "organization_id": f.organization_id, "case_id": f.id,
                                "program_id": f.program_id, "is_primary": True, "source": "manual"}
                               for f in filas])


def downgrade() -> None:
    op.drop_table("case_programs")
