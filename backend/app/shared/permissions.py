"""Catálogo de permisos, módulos y matriz rol → permiso.

Tres estructuras, cada una con una responsabilidad:

- `PERMISSION_CATALOG`: qué permisos existen. Un permiso es solo un código y su
  descripción; no sabe dónde se muestra.
- `DEFAULT_MODULES`: los grupos de permisos que trae el sistema. **El módulo
  tiene la lista de permisos**, no al revés, porque la relación es de muchos a
  muchos: un mismo permiso puede pertenecer a varios módulos
  (`dashboards.finance` está en Facturación y en Reportes; `programs.read` en
  Expedientes y en Configuración).
- `DEFAULT_ROLE_PERMISSIONS`: la matriz inicial rol → permiso, que es solo el
  punto de partida del seed. A partir de ahí se administra desde la aplicación
  (tablas `roles`, `role_permissions`, `user_roles`, el equivalente del sistema
  de Groups de Django).

El módulo es la unidad de navegación: el menú y las rutas del frontend
preguntan "¿este usuario tiene algún permiso de este módulo?" en vez de
preguntar por permisos sueltos. Los módulos se guardan en las tablas
`permission_modules` y `permission_module_items` y se administran desde la
pantalla de Módulos (decisión D9); lo que hay aquí son los valores iniciales
que siembra `scripts/seed.py`, igual que `DEFAULT_ROLE_PERMISSIONS` es el
valor inicial de los roles.

Los módulos salen de los cuatro bloques de "Funcionalidades requeridas" del PDF
`Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf` (vendedores §2, administrativo §3,
contable §4, técnicos §5). Dos capacidades van en módulos distintos cuando los
roles que las necesitan son distintos: por eso los gastos de campo no están
dentro de facturación (los carga el técnico desde el móvil, §4.1) y los
permisos municipales no están dentro de proyectos (los lleva Administración,
§3.2 y §3.5).

La autorización fina ("el técnico ve solo sus proyectos asignados") no es un
permiso: es un filtro en el selector del módulo correspondiente.

Ver `docs/PERMISOS.md` y
`docs/superpowers/specs/2026-09-22-modulo-0-roles-design.md`.
"""
from collections.abc import Iterable, Mapping
from typing import NamedTuple

# --------------------------------------------------------------------------
# Qué permisos existen
# --------------------------------------------------------------------------

PERMISSION_CATALOG: list[tuple[str, str]] = [
    # Prospectos y clientes (PDF §2.3)
    ("leads.manage", "Gestionar prospectos"),
    ("customers.create", "Crear clientes"),
    ("customers.read", "Ver clientes"),
    ("customers.update", "Editar clientes"),
    ("customers.delete", "Eliminar clientes"),
    ("contacts.manage", "Gestionar contactos del cliente"),
    ("activities.manage", "Gestionar actividades"),
    # Expedientes (PDF §3, "Dashboard centralizado")
    ("cases.create", "Crear expedientes"),
    ("cases.read_own", "Ver los expedientes propios"),
    ("cases.read_all", "Ver todos los expedientes"),
    ("cases.submit", "Enviar expedientes a revisión"),
    ("cases.review", "Revisar y devolver expedientes"),
    ("cases.approve", "Aprobar o rechazar expedientes"),
    ("cases.close_admin", "Cerrar expedientes administrativamente"),
    ("dashboards.commercial", "Ver el tablero comercial"),
    # Obsoletos: se retiran con Opportunity/Quote en el módulo 1 (decisión D2).
    ("opportunities.manage", "Gestionar oportunidades (obsoleto)"),
    ("quotes.manage", "Gestionar cotizaciones (obsoleto)"),
    # Documentos (PDF §3, "Gestor documental inteligente")
    ("documents.manage", "Cargar y reemplazar documentos"),
    ("documents.review", "Aceptar o rechazar documentos"),
    # Proyectos e instalación (PDF §5)
    ("projects.create", "Crear proyectos"),
    ("projects.read_all", "Ver todos los proyectos"),
    ("projects.read_assigned", "Ver los proyectos asignados"),
    ("projects.update", "Editar proyectos"),
    ("projects.assign", "Asignar personas a proyectos"),
    ("projects.close", "Cerrar proyectos"),
    ("tasks.manage", "Gestionar tareas"),
    ("checklists.manage", "Administrar plantillas de checklist"),
    # Reservado para el módulo 5: hoy `PATCH /checklist-items/{id}` exige
    # `checklists.manage`, que también permite crear plantillas, así que el
    # técnico no puede completar su propio checklist (PDF §5.5). Cuando la
    # Cadena B parta ese endpoint, este es el código que debe exigir.
    ("checklists.complete", "Completar ítems del checklist en campo"),
    ("checklists.approve", "Aprobar checklists"),
    ("evidence.create", "Cargar evidencias"),
    ("evidence.read_all", "Ver todas las evidencias"),
    ("evidence.read_assigned", "Ver evidencias de proyectos asignados"),
    ("evidence.delete", "Eliminar evidencias"),
    ("equipment.manage", "Registrar equipos instalados"),
    # Agenda y despacho (PDF §5.1, "Field Service Dispatch")
    ("dispatch.manage", "Programar y despachar órdenes"),
    ("dispatch.read_own", "Ver la agenda propia"),
    ("dashboards.operations", "Ver el monitor de operación"),
    # Permisos e inspecciones (PDF §3.2 y §3.5)
    ("permits.manage", "Gestionar permisos municipales"),
    ("inspections.manage", "Gestionar inspecciones"),
    # Facturación y cobros (PDF §3.4 y §4.2-4.3)
    ("invoices.create", "Crear facturas"),
    ("invoices.read", "Ver facturas"),
    ("invoices.update", "Editar facturas"),
    ("invoices.record_payment", "Registrar pagos"),
    ("invoices.export", "Exportar facturas"),
    ("billing.submit", "Radicar el cobro ante el programa"),
    ("dashboards.finance", "Ver el tablero financiero"),
    # Gastos de campo (PDF §4.1)
    ("expenses.create_own", "Registrar gastos propios"),
    ("expenses.read_all", "Ver todos los gastos"),
    ("expenses.approve", "Aprobar gastos"),
    # Proveedores y pagos (PDF §4.4)
    ("suppliers.manage", "Gestionar proveedores"),
    ("payables.manage", "Gestionar cuentas por pagar"),
    # Conciliación y rentabilidad (PDF §4.5)
    ("reconciliation.manage", "Conciliar pagos y movimientos"),
    ("profitability.read", "Ver la rentabilidad por proyecto"),
    ("accounting.export", "Exportar información contable"),
    # Reportes e indicadores (PDF §4.5 y §7)
    ("reports.view", "Ver reportes"),
    ("reports.generate", "Generar reportes"),
    ("reports.export", "Exportar reportes"),
    # Configuración de programas (Cadena A, módulo 1)
    ("programs.read", "Ver programas"),
    ("programs.manage", "Administrar programas"),
    ("fields.manage", "Administrar el catálogo de campos"),
    ("fields.view_sensitive", "Ver campos sensibles"),
    ("workflows.manage", "Administrar flujos y formularios"),
    ("workflows.publish", "Publicar versiones de flujo"),
    ("zones.manage", "Administrar zonas y asignación de vendedores"),
    ("settings.manage", "Administrar la configuración de la organización"),
    ("organization.manage", "Administrar la organización"),
    # Usuarios y roles
    ("users.manage", "Administrar usuarios"),
    ("roles.manage", "Administrar roles y permisos"),
    # Auditoría
    ("audit.read", "Ver la auditoría"),
    # Notificaciones (PDF §3)
    ("notifications.manage", "Administrar notificaciones"),
    ("notifications.read_own", "Ver las notificaciones propias"),
    # Perfil propio
    ("profile.manage", "Editar el perfil propio"),
]

# Permisos que a propósito no pertenecen a ningún módulo: los tiene todo rol y
# no encienden ningún ítem del menú.
STANDALONE_PERMISSIONS: set[str] = {"profile.manage"}


# --------------------------------------------------------------------------
# Grupos de permisos (módulos). El módulo tiene sus permisos; un permiso puede
# estar en varios módulos.
# --------------------------------------------------------------------------


class Module(NamedTuple):
    label: str
    permissions: list[str]


DEFAULT_MODULES: dict[str, Module] = {
    # --- Operación comercial ---
    "customers": Module(
        "Prospectos y clientes",
        [
            "leads.manage",
            "customers.create",
            "customers.read",
            "customers.update",
            "customers.delete",
            "contacts.manage",
            "activities.manage",
        ],
    ),
    "cases": Module(
        "Expedientes",
        [
            "cases.create",
            "cases.read_own",
            "cases.read_all",
            "cases.submit",
            "cases.review",
            "cases.approve",
            "cases.close_admin",
            "dashboards.commercial",
            "opportunities.manage",
            "quotes.manage",
            # El vendedor elige el programa desde el expediente.
            "programs.read",
            # Administración revisa las evidencias dentro del expediente.
            "evidence.read_all",
        ],
    ),
    "documents": Module(
        "Documentos",
        ["documents.manage", "documents.review"],
    ),
    # --- Operación de campo ---
    "projects": Module(
        "Proyectos e instalación",
        [
            "projects.create",
            "projects.read_all",
            "projects.read_assigned",
            "projects.update",
            "projects.assign",
            "projects.close",
            "tasks.manage",
            "checklists.manage",
            "checklists.complete",
            "checklists.approve",
            "evidence.create",
            "evidence.read_all",
            "evidence.read_assigned",
            "evidence.delete",
            "equipment.manage",
        ],
    ),
    "dispatch": Module(
        "Agenda y despacho",
        ["dispatch.manage", "dispatch.read_own", "dashboards.operations"],
    ),
    "permits": Module(
        "Permisos e inspecciones",
        ["permits.manage", "inspections.manage"],
    ),
    # --- Finanzas ---
    "billing": Module(
        "Facturación y cobros",
        [
            "invoices.create",
            "invoices.read",
            "invoices.update",
            "invoices.record_payment",
            "invoices.export",
            "billing.submit",
            "dashboards.finance",
        ],
    ),
    "expenses": Module(
        "Gastos de campo",
        ["expenses.create_own", "expenses.read_all", "expenses.approve"],
    ),
    "payables": Module(
        "Proveedores y pagos",
        ["suppliers.manage", "payables.manage"],
    ),
    "finance_close": Module(
        "Conciliación y rentabilidad",
        ["reconciliation.manage", "profitability.read", "accounting.export"],
    ),
    # --- Administración ---
    "reports": Module(
        "Reportes e indicadores",
        [
            "reports.view",
            "reports.generate",
            "reports.export",
            # Los tableros también se consultan desde Reportes.
            "dashboards.commercial",
            "dashboards.operations",
            "dashboards.finance",
            "profitability.read",
        ],
    ),
    "config": Module(
        "Configuración de programas",
        [
            # `programs.read` NO va aquí: leer el catálogo es parte de trabajar
            # un expediente (vive en `cases`), no de administrar el programa.
            # Estaba en los dos y le encendía este módulo entero al vendedor.
            "programs.manage",
            "fields.manage",
            "fields.view_sensitive",
            "workflows.manage",
            "workflows.publish",
            "zones.manage",
            "settings.manage",
            "organization.manage",
        ],
    ),
    "team": Module(
        "Usuarios y roles",
        ["users.manage", "roles.manage"],
    ),
    "audit": Module(
        "Auditoría",
        ["audit.read"],
    ),
    "notifications": Module(
        "Notificaciones",
        ["notifications.manage", "notifications.read_own"],
    ),
}


# --------------------------------------------------------------------------
# Roles del sistema y matriz inicial
# --------------------------------------------------------------------------

# Roles fieles a las áreas del PDF (decisión D1). `field_technician` conserva su
# código original porque el monitor de técnicos (Cadena B) lo referencia
# directamente; solo cambió su etiqueta.
ROLE_LABELS: dict[str, str] = {
    "organization_admin": "Administrador",
    "salesperson": "Vendedor",
    "admin_staff": "Administración",
    "field_technician": "Técnico",
    "accounting": "Contabilidad",
    "management": "Gerencia",
}

_ALL_PERMISSIONS = [code for code, _ in PERMISSION_CATALOG]

DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "organization_admin": _ALL_PERMISSIONS,
    "salesperson": [
        "leads.manage",
        "customers.create",
        "customers.read",
        "customers.update",
        "contacts.manage",
        "activities.manage",
        "cases.create",
        "cases.read_own",
        "cases.submit",
        "documents.manage",
        "programs.read",
        "expenses.create_own",
        "notifications.read_own",
        "profile.manage",
    ],
    "admin_staff": [
        "leads.manage",
        "customers.create",
        "customers.read",
        "customers.update",
        "contacts.manage",
        "activities.manage",
        "cases.read_all",
        "cases.review",
        "cases.approve",
        "cases.close_admin",
        "dashboards.commercial",
        "documents.manage",
        "documents.review",
        "projects.create",
        "projects.read_all",
        "projects.update",
        "projects.assign",
        "projects.close",
        "tasks.manage",
        "checklists.manage",
        "checklists.complete",
        "checklists.approve",
        "evidence.read_all",
        "equipment.manage",
        "dispatch.manage",
        "dashboards.operations",
        "permits.manage",
        "inspections.manage",
        "invoices.read",
        "billing.submit",
        "reports.view",
        "programs.read",
        "audit.read",
        "notifications.manage",
        "profile.manage",
    ],
    "field_technician": [
        "customers.read",
        "projects.read_assigned",
        "tasks.manage",
        "checklists.complete",
        "evidence.create",
        "evidence.read_assigned",
        "equipment.manage",
        "dispatch.read_own",
        "expenses.create_own",
        "notifications.read_own",
        "profile.manage",
    ],
    "accounting": [
        "customers.read",
        "cases.read_all",
        "projects.read_all",
        "invoices.create",
        "invoices.read",
        "invoices.update",
        "invoices.record_payment",
        "invoices.export",
        "billing.submit",
        "dashboards.finance",
        "expenses.read_all",
        "expenses.approve",
        "suppliers.manage",
        "payables.manage",
        "reconciliation.manage",
        "profitability.read",
        "accounting.export",
        "reports.view",
        "reports.generate",
        "reports.export",
        "audit.read",
        "notifications.read_own",
        "profile.manage",
    ],
    "management": [
        "customers.read",
        "cases.read_all",
        "dashboards.commercial",
        "projects.read_all",
        "evidence.read_all",
        "dashboards.operations",
        "invoices.read",
        "dashboards.finance",
        "profitability.read",
        "reports.view",
        "reports.generate",
        "reports.export",
        "audit.read",
        "notifications.read_own",
        "profile.manage",
    ],
}


def modules_for_permissions(
    codes: Iterable[str], modules: Mapping[str, Module] | None = None
) -> set[str]:
    """Módulos con al menos un permiso entre `codes`.

    Es lo que el frontend usa para decidir qué ítems del menú mostrar y qué
    rutas permitir. Un permiso suelto (`profile.manage`) no habilita nada en el
    menú, y un permiso que está en varios módulos los enciende todos.

    Es una función pura: recibe el mapa de módulos. En producción se le pasa el
    que arma el selector desde `permission_modules` (los módulos de esa
    organización, que el administrador pudo haber editado); sin argumento usa
    los valores por defecto del sistema."""
    held = set(codes)
    catalog = DEFAULT_MODULES if modules is None else modules
    return {key for key, module in catalog.items() if held & set(module.permissions)}


def permissions_of_module(
    key: str, modules: Mapping[str, Module] | None = None
) -> list[str]:
    """Permisos que componen un módulo, en el orden declarado."""
    catalog = DEFAULT_MODULES if modules is None else modules
    module = catalog.get(key)
    return list(module.permissions) if module else []
