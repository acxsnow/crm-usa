"""Órdenes de salida de bodega (punto 1 del cuestionario del 19 de octubre).

Crea las dos tablas de la orden de salida —la cabecera y sus líneas— y el
vínculo con la obra: `project_materials.warehouse_release_line_id` apunta a la
línea que entregó el material, que es lo que permite ver de qué orden salió cada
cosa cuando la instalación ya está cerrada.

No crea permisos ni módulos: la 0027 ya dejó `warehouse.request_release`,
`warehouse.approve_release` y `warehouse.deliver` y el módulo «Bodega».

Revision ID: 0028
Revises: 0027
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID
QUANTITY = sa.Numeric(10, 2)


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "warehouse_release_orders", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        # Nulo mientras es borrador: el número se asigna al mandarla a autorizar.
        sa.Column("number", sa.String(40)),
        sa.Column("status", sa.String(20), nullable=False, server_default="borrador"),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), index=True),
        sa.Column("location_id", GUID(), sa.ForeignKey("warehouse_locations.id"), nullable=False, index=True),
        sa.Column("requested_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("technician_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("needed_on", sa.Date()),
        sa.Column("note", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("authorized_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("authorized_at", sa.DateTime(timezone=True)),
        sa.Column("reject_reason", sa.Text()),
        sa.Column("delivered_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("shortage_note", sa.Text()),
        sa.UniqueConstraint("organization_id", "number", name="uq_warehouse_release_number"),
    )
    op.create_index("ix_warehouse_release_org_status", "warehouse_release_orders",
                    ["organization_id", "status"])
    op.create_table(
        "warehouse_release_lines", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("order_id", GUID(), sa.ForeignKey("warehouse_release_orders.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("item_id", GUID(), sa.ForeignKey("warehouse_items.id"), nullable=False, index=True),
        sa.Column("quantity_requested", QUANTITY, nullable=False),
        # Nulo hasta que Bodega entrega; cuando faltó existencia queda por debajo.
        sa.Column("quantity_delivered", QUANTITY),
        sa.Column("spec_label", sa.String(60)),
        sa.Column("notes", sa.Text()),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_warehouse_release_lines_org_order", "warehouse_release_lines",
                    ["organization_id", "order_id"])

    op.add_column("project_materials", sa.Column("warehouse_release_line_id", GUID(), nullable=True))
    op.create_index("ix_project_materials_warehouse_release_line_id", "project_materials",
                    ["warehouse_release_line_id"])


def downgrade() -> None:
    op.drop_index("ix_project_materials_warehouse_release_line_id", table_name="project_materials")
    op.drop_column("project_materials", "warehouse_release_line_id")

    op.drop_index("ix_warehouse_release_lines_org_order", table_name="warehouse_release_lines")
    op.drop_table("warehouse_release_lines")
    op.drop_index("ix_warehouse_release_org_status", table_name="warehouse_release_orders")
    op.drop_table("warehouse_release_orders")
