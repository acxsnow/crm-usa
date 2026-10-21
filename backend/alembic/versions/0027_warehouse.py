"""Bodega: catálogo de materiales, ubicaciones, existencias y movimientos
(spec `2026-10-19-control-bodega-design.md`, fase 0).

Crea las cuatro tablas de la bodega, los permisos nuevos, el módulo «Bodega» y
la concesión inicial a los roles del PDF. Como en la 0025, la concesión solo
inserta lo que falta: si un administrador ya editó la matriz de roles, esta
migración no se la pisa.

Revision ID: 0027
Revises: 0026
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID
MONEY = sa.Numeric(12, 2)
QUANTITY = sa.Numeric(10, 2)

MODULE_KEY = "warehouse"

NEW_PERMISSIONS: dict[str, str] = {
    "warehouse.read": "Ver el catálogo, las existencias y los movimientos de bodega",
    "warehouse.manage": "Administrar el catálogo, ubicaciones, entradas y cargas del Excel",
    "warehouse.kits_manage": "Administrar las listas predefinidas por tipo de trabajo",
    "warehouse.request_release": "Pedir una salida de material de bodega",
    "warehouse.approve_release": "Autorizar o rechazar una salida de material",
    "warehouse.deliver": "Entregar el material de una salida autorizada",
    "warehouse.count": "Registrar el conteo físico de la bodega",
    "budgets.manage": "Armar el presupuesto de un proyecto",
    "budgets.approve": "Aprobar el presupuesto de un proyecto",
    "daylogs.manage": "Registrar el diario de obra (jornadas de un proyecto)",
}

# Orden en que se ven dentro del módulo. Debe seguir a `DEFAULT_MODULES`.
MODULE_PERMISSIONS: list[str] = [
    "warehouse.read", "warehouse.manage", "warehouse.kits_manage", "warehouse.request_release",
    "warehouse.approve_release", "warehouse.deliver", "warehouse.count", "budgets.manage",
    "budgets.approve", "daylogs.manage",
]


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def _grant_permissions(conn) -> None:
    """Inserta los permisos nuevos y los concede a los roles que la matriz
    inicial les da. Solo agrega lo que falta."""
    from app.shared.permissions import DEFAULT_ROLE_PERMISSIONS

    for code, description in NEW_PERMISSIONS.items():
        conn.execute(sa.text(
            "INSERT INTO permissions (id, code, description)"
            " SELECT gen_random_uuid(), :code, :description"
            " WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
        ).bindparams(code=code, description=description))

    for role_code, codes in DEFAULT_ROLE_PERMISSIONS.items():
        for code in codes:
            if code not in NEW_PERMISSIONS:
                continue
            conn.execute(sa.text(
                "INSERT INTO role_permissions (role_id, permission_id)"
                " SELECT r.id, p.id FROM roles r, permissions p"
                " WHERE r.code = :role AND p.code = :perm"
                "   AND NOT EXISTS (SELECT 1 FROM role_permissions rp"
                "                   WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ).bindparams(role=role_code, perm=code))


def _create_module(conn) -> None:
    """El módulo «Bodega» como plantilla del sistema y como copia de cada
    organización que ya existe (mismo patrón que los roles, decisión D9)."""
    from app.shared.permissions import DEFAULT_MODULES

    orden = list(DEFAULT_MODULES).index(MODULE_KEY)
    permission_ids = {row[0]: row[1] for row in conn.execute(sa.text("SELECT code, id FROM permissions"))}
    organizaciones: list[uuid.UUID | None] = [None]
    organizaciones += [row[0] for row in conn.execute(sa.text("SELECT id FROM organizations"))]

    for organization_id in organizaciones:
        if organization_id is None:
            existente = conn.execute(sa.text(
                "SELECT id FROM permission_modules WHERE key = :key AND organization_id IS NULL"
            ).bindparams(key=MODULE_KEY)).scalar()
        else:
            existente = conn.execute(sa.text(
                "SELECT id FROM permission_modules WHERE key = :key AND organization_id = :org"
            ).bindparams(key=MODULE_KEY, org=organization_id)).scalar()

        if existente is None:
            existente = uuid.uuid4()
            conn.execute(sa.text(
                "INSERT INTO permission_modules"
                " (id, organization_id, key, label, sort_order, is_system, created_at, updated_at)"
                " VALUES (:id, :org, :key, 'Bodega', :sort, true, now(), now())"
            ).bindparams(id=existente, org=organization_id, key=MODULE_KEY, sort=orden))

        for posicion, code in enumerate(MODULE_PERMISSIONS):
            permission_id = permission_ids.get(code)
            if permission_id is None:
                continue
            conn.execute(sa.text(
                "INSERT INTO permission_module_items (id, module_id, permission_id, sort_order)"
                " SELECT gen_random_uuid(), :module, :perm, :sort"
                " WHERE NOT EXISTS (SELECT 1 FROM permission_module_items"
                "                   WHERE module_id = :module AND permission_id = :perm)"
            ).bindparams(module=existente, perm=permission_id, sort=posicion))


def upgrade() -> None:
    op.create_table(
        "warehouse_locations", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="warehouse"),
        sa.Column("technician_user_id", GUID(), sa.ForeignKey("users.id"), index=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "name", name="uq_warehouse_location_name"),
    )
    op.create_table(
        "warehouse_items", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(255), nullable=False), sa.Column("sku", sa.String(80)),
        sa.Column("category", sa.String(30), nullable=False, server_default="other"),
        sa.Column("unit", sa.String(20), nullable=False, server_default="unit"),
        sa.Column("unit_cost", MONEY, nullable=False, server_default="0"),
        sa.Column("supplier_name", sa.String(255)),
        sa.Column("has_serial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_quantity", QUANTITY), sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "sku", name="uq_warehouse_item_sku"),
    )
    op.create_index("ix_warehouse_items_org_category", "warehouse_items", ["organization_id", "category"])
    op.create_table(
        "warehouse_stock", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("item_id", GUID(), sa.ForeignKey("warehouse_items.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("location_id", GUID(), sa.ForeignKey("warehouse_locations.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("quantity", QUANTITY, nullable=False, server_default="0"),
        sa.UniqueConstraint("item_id", "location_id", name="uq_warehouse_stock_item_location"),
    )
    op.create_table(
        "warehouse_movements", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("item_id", GUID(), sa.ForeignKey("warehouse_items.id"), nullable=False, index=True),
        sa.Column("location_id", GUID(), sa.ForeignKey("warehouse_locations.id"), nullable=False, index=True),
        sa.Column("to_location_id", GUID(), sa.ForeignKey("warehouse_locations.id")),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False), sa.Column("unit_cost", MONEY),
        sa.Column("movement_date", sa.Date(), nullable=False), sa.Column("reference", sa.String(120)),
        sa.Column("note", sa.Text()), sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), index=True),
        sa.Column("source_key", sa.String(160)),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "source_key", name="uq_warehouse_movement_source"),
    )
    op.create_index("ix_warehouse_movements_org_date", "warehouse_movements", ["organization_id", "movement_date"])
    op.create_index("ix_warehouse_movements_org_item", "warehouse_movements", ["organization_id", "item_id"])

    conn = op.get_bind()
    _grant_permissions(conn)
    _create_module(conn)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM permission_module_items WHERE module_id IN"
        " (SELECT id FROM permission_modules WHERE key = :key)"
    ).bindparams(key=MODULE_KEY))
    conn.execute(sa.text("DELETE FROM permission_modules WHERE key = :key").bindparams(key=MODULE_KEY))
    for code in NEW_PERMISSIONS:
        conn.execute(sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN"
            " (SELECT id FROM permissions WHERE code = :code)"
        ).bindparams(code=code))
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))

    op.drop_index("ix_warehouse_movements_org_item", table_name="warehouse_movements")
    op.drop_index("ix_warehouse_movements_org_date", table_name="warehouse_movements")
    op.drop_table("warehouse_movements")
    op.drop_table("warehouse_stock")
    op.drop_index("ix_warehouse_items_org_category", table_name="warehouse_items")
    op.drop_table("warehouse_items")
    op.drop_table("warehouse_locations")
