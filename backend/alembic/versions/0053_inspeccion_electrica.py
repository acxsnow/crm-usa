"""Inspección eléctrica antes de la instalación (cliente, 5 nov 2026): la visita
del técnico que dice si la casa es viable y a qué beneficios aplica.

Revision ID: 0053
Revises: 0052
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.db.types import GUID

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "electrical_inspections",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("case_id", GUID(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("technician_user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text()),
        sa.Column("scheduled_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("panel_amperage", sa.String(20)),
        sa.Column("viability", sa.String(20)),
        sa.Column("tons", sa.Numeric(4, 1)),
        sa.Column("water_heater_eligible", sa.Boolean()),
        sa.Column("induction_eligible", sa.Boolean()),
        sa.Column("result_notes", sa.Text()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("cancel_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("electrical_inspections")
