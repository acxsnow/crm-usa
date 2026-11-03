"""Decisiones de Don Aldo en turnos (D-019).

- `employee_pay_settings`: forma de pago por persona; define si el almuerzo va incluido.
- `overtime_declarations`: horas extras declaradas, con el valor que define el jefe.
- La marcación obligatoria queda encendida, también para las organizaciones que ya existen.
- Gerencia deja de ver el mapa operativo: se le quita `locations.view`.

Revision ID: 0047
Revises: 0046
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "employee_pay_settings", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pay_type", sa.String(10), nullable=False),
        sa.Column("updated_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_employee_pay_user"),
    )
    op.create_table(
        "overtime_declarations", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("value_amount", sa.Numeric(12, 2)),
        sa.Column("review_notes", sa.String(500)),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "user_id", "work_date", name="uq_overtime_user_day"),
    )
    op.create_index("ix_overtime_org_date", "overtime_declarations", ["organization_id", "work_date"])
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE attendance_settings SET require_clock_in_for_field_work = true"))
    conn.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'locations.view')"
        " AND role_id IN (SELECT id FROM roles WHERE code = 'management')"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r, permissions p"
        " WHERE r.code = 'management' AND p.code = 'locations.view' AND NOT EXISTS (SELECT 1 FROM role_permissions rp"
        "   WHERE rp.role_id = r.id AND rp.permission_id = p.id)"))
    conn.execute(sa.text("UPDATE attendance_settings SET require_clock_in_for_field_work = false"))
    op.drop_index("ix_overtime_org_date", table_name="overtime_declarations")
    op.drop_table("overtime_declarations")
    op.drop_table("employee_pay_settings")
