"""Recepción de compras en bodega, con llegadas parciales, y el motivo de cada
ajuste de existencias (cuestionario de bodega, 26 nov 2026).

Revision ID: 0054
Revises: 0053
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.db.types import GUID

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tiempos():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.add_column("warehouse_movements", sa.Column("reason", sa.String(30)))
    op.create_table(
        "warehouse_receipts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("supplier_id", GUID(), sa.ForeignKey("suppliers.id"), index=True),
        sa.Column("supplier_name", sa.String(255)),
        sa.Column("document_number", sa.String(80)),
        sa.Column("document_date", sa.Date()),
        sa.Column("location_id", GUID(), sa.ForeignKey("warehouse_locations.id"), nullable=False),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("shipping", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="abierta"),
        sa.Column("note", sa.Text()),
        sa.Column("close_reason", sa.Text()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("supplier_invoice_id", GUID(), sa.ForeignKey("supplier_invoices.id"), index=True),
        sa.Column("invoice_linked_at", sa.DateTime(timezone=True)),
        sa.Column("invoice_linked_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
        *_tiempos(),
        sa.UniqueConstraint("organization_id", "number", name="uq_warehouse_receipt_number"),
    )
    op.create_index("ix_warehouse_receipts_org_status", "warehouse_receipts", ["organization_id", "status"])
    op.create_table(
        "warehouse_receipt_lines",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("receipt_id", GUID(), sa.ForeignKey("warehouse_receipts.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("item_id", GUID(), sa.ForeignKey("warehouse_items.id"), nullable=False, index=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ordered_quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("received_quantity", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        *_tiempos(),
    )


def downgrade() -> None:
    op.drop_table("warehouse_receipt_lines")
    op.drop_index("ix_warehouse_receipts_org_status", table_name="warehouse_receipts")
    op.drop_table("warehouse_receipts")
    op.drop_column("warehouse_movements", "reason")
