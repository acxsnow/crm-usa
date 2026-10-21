"""El técnico ya no tiene `warehouse.read`: veía existencias, movimientos y
costos de bodega. El catálogo (sin costos) le llega por
`warehouse.request_release` y `daylogs.manage`.

Revision ID: 0032
Revises: 0031
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLE = "field_technician"
_PERMISSION = "warehouse.read"


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "DELETE FROM role_permissions"
        " WHERE role_id IN (SELECT id FROM roles WHERE code = :role)"
        "   AND permission_id IN (SELECT id FROM permissions WHERE code = :perm)"
    ).bindparams(role=_ROLE, perm=_PERMISSION))


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id)"
        " SELECT r.id, p.id FROM roles r, permissions p"
        " WHERE r.code = :role AND p.code = :perm"
        "   AND NOT EXISTS (SELECT 1 FROM role_permissions rp"
        "                   WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
    ).bindparams(role=_ROLE, perm=_PERMISSION))
