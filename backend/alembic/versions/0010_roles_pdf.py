"""Roles del flujo operativo de Delta HVAC

Reemplaza los roles genéricos del CRM original por los del PDF (decisión D1):
Administrador, Vendedor, Administración, Técnico, Contabilidad y Gerencia.

Qué hace, en orden:

1. Inserta los permisos del catálogo que falten.
2. Crea los roles nuevos que falten, como plantilla (`organization_id` nulo) y
   como copia de cada organización.
3. Sincroniza `role_permissions` de los seis roles con la matriz inicial. Es
   una migración de línea base: se corre cuando nadie ha editado todavía la
   matriz desde la aplicación. **Después de esto, editar permisos es trabajo
   del administrador y ninguna migración vuelve a sobrescribirlos.**
4. Reasigna los usuarios de los roles viejos al rol nuevo equivalente.
5. Borra los roles viejos y sus asignaciones.

El mapa `OLD_TO_NEW` está escrito aquí y no importado, porque es propio de esta
migración. La matriz sí se importa de `app.shared.permissions` para no
duplicarla: el objetivo es justamente dejar la base igual que el catálogo.

`platform_super_admin` se retira como rol: sigue existiendo como la bandera
`users.is_platform_super_admin`, que es donde el código la consulta.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-23
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Rol viejo → rol nuevo al que pasan sus usuarios. None = no se reasigna a
# nadie (la capacidad vive ahora en una bandera del usuario).
OLD_TO_NEW: dict[str, str | None] = {
    "commercial_manager": "salesperson",
    "project_manager": "admin_staff",
    "supervisor": "admin_staff",
    "finance_user": "accounting",
    "read_only": "management",
    "platform_super_admin": None,
}

# Matriz anterior, solo para poder deshacer la migración.
LEGACY_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "commercial_manager": [
        "customers.create", "customers.read", "customers.update",
        "contacts.manage", "leads.manage", "opportunities.manage",
        "quotes.manage", "activities.manage",
        "projects.read_all", "invoices.read", "dashboards.commercial",
    ],
    "project_manager": [
        "customers.read", "contacts.manage",
        "opportunities.manage", "quotes.manage",
        "projects.create", "projects.read_all", "projects.update",
        "projects.assign", "projects.close",
        "tasks.manage", "checklists.manage",
        "evidence.create", "evidence.read_all",
        "reports.generate", "reports.export",
        "invoices.read", "dashboards.operations",
    ],
    "supervisor": [
        "customers.read", "projects.read_assigned", "tasks.manage",
        "checklists.manage", "checklists.approve",
        "evidence.create", "evidence.read_assigned",
        "reports.generate", "invoices.read", "dashboards.operations",
    ],
    "finance_user": [
        "customers.read", "invoices.create", "invoices.read", "invoices.update",
        "invoices.record_payment", "invoices.export", "dashboards.finance",
    ],
    "read_only": [],
    "platform_super_admin": [],
}

LEGACY_ROLE_LABELS: dict[str, str] = {
    "commercial_manager": "Commercial Manager",
    "project_manager": "Project Manager",
    "supervisor": "Supervisor",
    "finance_user": "Finance User",
    "read_only": "Read Only",
    "platform_super_admin": "Platform Super Admin",
    "organization_admin": "Organization Admin",
    "field_technician": "Field Technician",
}


def _sync_roles(conn, role_permissions: dict[str, list[str]], role_labels: dict[str, str]) -> None:
    """Deja en la base exactamente los roles de `role_permissions`, con sus
    permisos y etiquetas, como plantilla y como copia de cada organización."""
    permission_ids = {
        row[0]: row[1] for row in conn.execute(sa.text("SELECT code, id FROM permissions"))
    }

    org_ids: list[uuid.UUID | None] = [None]
    org_ids += [row[0] for row in conn.execute(sa.text("SELECT id FROM organizations"))]

    for organization_id in org_ids:
        if organization_id is None:
            existing = {
                row[0]: row[1]
                for row in conn.execute(
                    sa.text("SELECT code, id FROM roles WHERE organization_id IS NULL")
                )
            }
        else:
            existing = {
                row[0]: row[1]
                for row in conn.execute(
                    sa.text("SELECT code, id FROM roles WHERE organization_id = :org"),
                    {"org": organization_id},
                )
            }

        for code, codes in role_permissions.items():
            role_id = existing.get(code)
            if role_id is None:
                role_id = uuid.uuid4()
                conn.execute(
                    sa.text(
                        "INSERT INTO roles (id, organization_id, code, name, is_system,"
                        " created_at, updated_at)"
                        " VALUES (:id, :org, :code, :name, true, now(), now())"
                    ),
                    {
                        "id": role_id,
                        "org": organization_id,
                        "code": code,
                        "name": role_labels[code],
                    },
                )
            else:
                conn.execute(
                    sa.text("UPDATE roles SET name = :name WHERE id = :id"),
                    {"name": role_labels[code], "id": role_id},
                )

            conn.execute(
                sa.text("DELETE FROM role_permissions WHERE role_id = :id"), {"id": role_id}
            )
            for permission_code in codes:
                permission_id = permission_ids.get(permission_code)
                if permission_id is None:
                    continue
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id)"
                        " VALUES (:role_id, :permission_id)"
                    ),
                    {"role_id": role_id, "permission_id": permission_id},
                )


def _reassign_and_drop(conn, mapping: dict[str, str | None]) -> None:
    """Mueve los usuarios de cada rol de `mapping` a su equivalente y borra el
    rol viejo. Si un usuario ya tenía el rol destino, no se duplica."""
    for old_code, new_code in mapping.items():
        old_roles = list(
            conn.execute(
                sa.text("SELECT id, organization_id FROM roles WHERE code = :code"),
                {"code": old_code},
            )
        )
        for old_id, organization_id in old_roles:
            if new_code is not None and organization_id is not None:
                new_id = conn.execute(
                    sa.text(
                        "SELECT id FROM roles WHERE code = :code AND organization_id = :org"
                    ),
                    {"code": new_code, "org": organization_id},
                ).scalar()
                if new_id is not None:
                    conn.execute(
                        sa.text(
                            "INSERT INTO user_roles (id, user_id, role_id)"
                            " SELECT gen_random_uuid(), ur.user_id, :new_id FROM user_roles ur"
                            " WHERE ur.role_id = :old_id"
                            "   AND NOT EXISTS ("
                            "     SELECT 1 FROM user_roles x"
                            "     WHERE x.user_id = ur.user_id AND x.role_id = :new_id)"
                        ),
                        {"new_id": new_id, "old_id": old_id},
                    )
            conn.execute(sa.text("DELETE FROM user_roles WHERE role_id = :id"), {"id": old_id})
            conn.execute(
                sa.text("DELETE FROM role_permissions WHERE role_id = :id"), {"id": old_id}
            )
            conn.execute(sa.text("DELETE FROM roles WHERE id = :id"), {"id": old_id})


def upgrade() -> None:
    from app.shared.permissions import (
        DEFAULT_ROLE_PERMISSIONS,
        PERMISSION_CATALOG,
        ROLE_LABELS,
    )

    conn = op.get_bind()

    existing = {row[0] for row in conn.execute(sa.text("SELECT code FROM permissions"))}
    for code, description in PERMISSION_CATALOG:
        if code not in existing:
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, description)"
                    " VALUES (:id, :code, :description)"
                ),
                {"id": uuid.uuid4(), "code": code, "description": description},
            )

    _sync_roles(conn, DEFAULT_ROLE_PERMISSIONS, ROLE_LABELS)
    _reassign_and_drop(conn, OLD_TO_NEW)


def downgrade() -> None:
    """Restaura los roles genéricos anteriores.

    Devuelve la estructura, no las asignaciones exactas: un usuario que estaba
    en `supervisor` y pasó a `admin_staff` vuelve a `admin_staff`, no a
    `supervisor`, porque esa información se pierde al fusionar dos roles en
    uno. Queda registrado aquí para que nadie espere lo contrario."""
    conn = op.get_bind()
    _sync_roles(conn, LEGACY_ROLE_PERMISSIONS, LEGACY_ROLE_LABELS)
    _reassign_and_drop(
        conn,
        {
            "salesperson": "commercial_manager",
            "admin_staff": "project_manager",
            "accounting": "finance_user",
            "management": "read_only",
        },
    )
