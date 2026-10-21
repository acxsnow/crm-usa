"""Listas predefinidas por tipo de trabajo (punto 2 del cuestionario del 19 de octubre).

El cliente lo pidió así: «aires y pedestales siempre llevan el mismo material, a
veces cambian algunas cantidades o calibres». La lista es la plantilla; al armar
una orden de salida (o un presupuesto) sus líneas se **copian** al documento, de
modo que editar la plantilla no cambia lo que ya se pidió. Es el mismo mecanismo
de `checklist_templates` → `project_checklist_items`.

No crea permisos ni módulos: la 0027 ya dejó `warehouse.kits_manage` y el módulo
«Bodega».

Revision ID: 0029
Revises: 0028
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0029"
down_revision: Union[str, None] = "0028"
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
        "warehouse_kit_templates", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("name", sa.String(255), nullable=False),
        # El tipo de trabajo del proyecto («hvac_install», «pedestal»...). Es el
        # texto libre que ya usa `projects.project_type`.
        sa.Column("project_type", sa.String(100), index=True),
        sa.Column("description", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "name", name="uq_warehouse_kit_name"),
    )
    op.create_table(
        "warehouse_kit_items", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("template_id", GUID(), sa.ForeignKey("warehouse_kit_templates.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("item_id", GUID(), sa.ForeignKey("warehouse_items.id"), nullable=False, index=True),
        sa.Column("quantity", QUANTITY, nullable=False, server_default="1"),
        # El calibre sugerido («3/8», «1/2»): lo que más cambia entre un trabajo
        # y otro y por eso se puede ajustar en cada copia.
        sa.Column("spec_label", sa.String(60)),
        # En qué parte del trabajo va («Unidad exterior», «Líneas»), para que la
        # lista se lea como el recorrido de la instalación.
        sa.Column("section", sa.String(120)),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_warehouse_kit_items_org_template", "warehouse_kit_items",
                    ["organization_id", "template_id"])


def downgrade() -> None:
    op.drop_index("ix_warehouse_kit_items_org_template", table_name="warehouse_kit_items")
    op.drop_table("warehouse_kit_items")
    op.drop_table("warehouse_kit_templates")
