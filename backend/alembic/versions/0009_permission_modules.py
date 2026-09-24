"""Módulos de permisos (grupos editables desde la aplicación)

Un módulo agrupa permisos y es la unidad de navegación: el menú y las rutas
preguntan "¿el usuario tiene algún permiso de este módulo?". La relación es de
muchos a muchos, por eso el detalle va en su propia tabla: el mismo permiso
puede pertenecer a varios módulos.

Mismo patrón que los roles: `organization_id` nulo es la plantilla del sistema
y cada organización recibe su copia editable. Decisión D9.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "permission_modules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), nullable=True, index=True),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("label", sa.String(150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "key", name="uq_permission_module_org_key"),
    )
    op.create_table(
        "permission_module_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "module_id",
            GUID(),
            sa.ForeignKey("permission_modules.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "permission_id",
            GUID(),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("module_id", "permission_id", name="uq_permission_module_item"),
    )


def downgrade() -> None:
    op.drop_table("permission_module_items")
    op.drop_table("permission_modules")
