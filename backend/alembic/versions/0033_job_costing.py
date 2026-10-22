"""Costo del trabajo: plantillas de costo, costos reales anotados a mano y
cobros adicionales (spec 2026-10-22).

- `project_budgets` gana `expected_revenue` (el precio esperado) y
  `template_id` (de qué plantilla salió el estimado).
- `cost_templates` / `cost_template_lines`: cómo se reparte el precio de un
  tipo de trabajo, por % o por monto.
- `project_cost_entries`: mano de obra, representante… (lo que en Housecall Pro
  es «Labor»). Interno: nunca va a la factura del cliente.
- `project_extra_charges`: lo que el dueño de casa paga aparte (casi siempre en
  efectivo), con su entrega a la oficina.

Las plantillas iniciales no se siembran aquí: se crean la primera vez que la
organización lista sus plantillas, así también las tienen las organizaciones
nuevas.

Revision ID: 0033
Revises: 0032
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID
MONEY = sa.Numeric(12, 2)


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "cost_templates", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("job_type", sa.String(100)),
        sa.Column("applies_to", sa.String(20), nullable=False, server_default="both"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "name", name="uq_cost_template_name"),
    )
    op.create_table(
        "cost_template_lines", sa.Column("id", GUID(), primary_key=True), *_stamps(),
        sa.Column("template_id", GUID(), sa.ForeignKey("cost_templates.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False, server_default="amount"),
        sa.Column("value", MONEY, nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("project_budgets", sa.Column("expected_revenue", MONEY))
    op.add_column("project_budgets", sa.Column("template_id", GUID(), sa.ForeignKey("cost_templates.id")))
    op.create_table(
        "project_cost_entries", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("person_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("person_name", sa.String(255)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_project_cost_entries_org_project", "project_cost_entries",
                    ["organization_id", "project_id"])
    op.create_table(
        "project_extra_charges", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("charge_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("received_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_to_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_project_extra_charges_org_project", "project_extra_charges",
                    ["organization_id", "project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_extra_charges_org_project", table_name="project_extra_charges")
    op.drop_table("project_extra_charges")
    op.drop_index("ix_project_cost_entries_org_project", table_name="project_cost_entries")
    op.drop_table("project_cost_entries")
    op.drop_column("project_budgets", "template_id")
    op.drop_column("project_budgets", "expected_revenue")
    op.drop_table("cost_template_lines")
    op.drop_table("cost_templates")
