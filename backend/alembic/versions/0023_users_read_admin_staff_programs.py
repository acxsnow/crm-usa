"""Permiso `users.read` y Administración con la configuración de programas.

- `users.read` («Ver la lista de usuarios»), en el módulo "Usuarios y roles":
  listar sin poder invitar, desactivar ni cambiar roles. Lo usan la asignación
  de vendedores a zonas y los filtros por persona de Proyectos y Auditoría.
- Administración recibe la configuración de programas completa (programas,
  campos, formularios, publicar versiones y zonas) y las respuestas sensibles
  del formulario para revisar la elegibilidad.

Solo agrega: no quita nada de lo que el Administrador haya ajustado en
«Roles y permisos». Todo en SQL puro, como la 0015, para que también se pueda
generar en modo offline (--sql).

Revision ID: 0023
Revises: 0022
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS = {
    "users.read": "Ver la lista de usuarios",
}
# Rol → permisos que se agregan (mismo reparto que DEFAULT_ROLE_PERMISSIONS).
# Se aplica a los roles del sistema y a las copias de cada organización.
_ROLE_GRANTS = {
    "organization_admin": ["users.read"],
    "admin_staff": [
        "programs.manage",
        "fields.manage",
        "fields.view_sensitive",
        "workflows.manage",
        "workflows.publish",
        "zones.manage",
        "users.read",
    ],
    "accounting": ["users.read"],
    "management": ["users.read"],
}
# Solo lo que esta migración agrega al rol; al revertir se quita únicamente eso.
_ADMIN_STAFF_REVERT = [p for p in _ROLE_GRANTS["admin_staff"] if p not in _NEW_PERMISSIONS]


def upgrade() -> None:
    for code, description in _NEW_PERMISSIONS.items():
        op.execute(sa.text(
            "INSERT INTO permissions (id, code, description) SELECT gen_random_uuid(), :code, :description "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
        ).bindparams(code=code, description=description))
    for role_code, codes in _ROLE_GRANTS.items():
        for code in codes:
            op.execute(sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p WHERE r.code = :role AND p.code = :perm "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ).bindparams(role=role_code, perm=code))
    for code in _NEW_PERMISSIONS:
        op.execute(sa.text(
            "INSERT INTO permission_module_items (id, module_id, permission_id, sort_order) "
            "SELECT gen_random_uuid(), m.id, p.id, 100 FROM permission_modules m, permissions p "
            "WHERE m.key = 'team' AND p.code = :perm "
            "AND NOT EXISTS (SELECT 1 FROM permission_module_items i WHERE i.module_id = m.id AND i.permission_id = p.id)"
        ).bindparams(perm=code))


def downgrade() -> None:
    for code in _ADMIN_STAFF_REVERT:
        op.execute(sa.text(
            "DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE code = 'admin_staff') "
            "AND permission_id IN (SELECT id FROM permissions WHERE code = :perm)"
        ).bindparams(perm=code))
    for code in _NEW_PERMISSIONS:
        # role_permissions y permission_module_items caen en cascada.
        op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
