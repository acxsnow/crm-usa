/**
 * Definición del menú y su construcción POR USUARIO.
 *
 * El menú no se escribe dentro del layout: se declara aquí y `buildNavForUser`
 * devuelve solo lo que ese usuario puede ver.
 *
 * **Cada ítem se habilita por el permiso que su pantalla realmente exige**, no
 * por el módulo al que pertenece. Los módulos (ver `docs/PERMISOS.md`) siguen
 * siendo la agrupación con la que el administrador *asigna* permisos a un rol
 * en la pantalla de Roles; pero no sirven para decidir qué se muestra, porque
 * `modules_for_permissions` abre un módulo con **cualquiera** de sus permisos.
 * El vendedor tiene `programs.read` para elegir el programa desde el
 * expediente, y eso le encendía el módulo `config` entero —
 * "Configuración de programas" le aparecía en el menú.
 *
 * Regla: un rol solo ve aquello para lo que tiene permiso.
 *
 * Varios permisos en un ítem se leen como "alguno de": Expedientes se muestra
 * con `cases.read_own` (el vendedor ve los suyos) o con `cases.read_all`
 * (administración los ve todos). Es la misma pantalla; qué devuelve depende
 * del backend, que filtra por permiso.
 *
 * Los módulos que todavía no existen quedan `disabled: true`: se ven en gris,
 * de modo que el mapa del sistema al que ese rol tendrá acceso está a la vista
 * desde el principio y quien lo construya solo tiene que quitar la marca.
 */
import type { CurrentUser } from "@/types/auth";

export interface NavItem {
  label: string;
  to: string;
  icon: string;
  /**
   * Permiso(s) que exige la pantalla. Un arreglo se lee como "alguno de".
   * Sin permiso declarado, el ítem es visible para cualquier sesión (Inicio).
   */
  permission?: string | string[];
  /** El módulo todavía no está construido. */
  disabled?: boolean;
}

export interface NavGroup {
  label?: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    items: [{ label: "Inicio", to: "/", icon: "⌂" }],
  },
  {
    label: "Operación comercial",
    items: [
      // NO hay ítem "Prospectos": `Lead` se retira. El expediente ES la puerta
      // desde el primer toque, así que un prospecto y un caso eran la misma cosa
      // con dos nombres. Ver `docs/superpowers/specs/2026-09-25-esqueleto-case-design.md`.
      { label: "Clientes", to: "/customers", icon: "♙", permission: "customers.read" },
      // Inicio del vendedor (módulo 2): sus programas, zonas y lo pendiente.
      { label: "Mi día", to: "/sales", icon: "☀", permission: "cases.create" },
      // Campañas de productos por SMS y correo, a clientes y contactos propios con permiso.
      { label: "Campañas", to: "/campaigns", icon: "✉", permission: "notifications.manage" },
      {
        // El centro del trabajo del vendedor: kanban de expedientes por etapa
        // (módulo 2). Reemplaza `/applications` del modelo anterior.
        label: "Expedientes",
        to: "/cases",
        icon: "✓",
        permission: ["cases.read_own", "cases.read_all"],
      },
      // NO hay ítem "Pipeline": `Opportunity` se retira. Su reemplazo es el
      // tablero de expedientes por etapa, dentro de Expedientes (módulo 2).
      {
        // La bandeja diaria de Administración (spec 2026-10-19-bandeja-por-revisar):
        // documentos, actas por confirmar, inspección municipal y cobros por
        // crear. Se ve con cualquiera de esos permisos; al vendedor no le sirve.
        label: "Por revisar",
        to: "/review",
        icon: "🗎",
        permission: ["documents.review", "checklists.approve", "inspections.manage", "billing.submit"],
      },
    ],
  },
  {
    label: "Operación de campo",
    items: [
      {
        label: "Proyectos",
        to: "/projects",
        icon: "▣",
        permission: ["projects.read_all", "projects.read_assigned"],
      },
      // Vista de supervisión de todo el equipo: su endpoint exige
      // `dashboards.operations`, que el técnico no tiene.
      {
        label: "Monitor de técnicos",
        to: "/technician-monitor",
        icon: "◉",
        permission: "dashboards.operations",
      },
      // El técnico ve la suya; Administración (`dispatch.manage`) la de todos.
      {
        label: "Agenda",
        to: "/my-schedule",
        icon: "◷",
        permission: ["dispatch.read_own", "dispatch.manage"],
      },
      // Quién estuvo en cada obra y qué se hizo cada día (plan bodega-cierre, fase 5).
      {
        label: "Calendario de obras",
        to: "/works-calendar",
        icon: "▦",
        permission: ["projects.read_all", "dispatch.manage", "daylogs.manage"],
      },
      // Plantillas de checklist por programa (módulo 5).
      { label: "Checklists de instalación", to: "/checklists", icon: "☑", permission: "checklists.manage" },
      {
        label: "Permisos e inspecciones",
        to: "/permits",
        icon: "◪",
        permission: ["permits.manage", "inspections.manage", "projects.read_all"],
      },
    ],
  },
  {
    // Turnos, asistencia y nómina (spec 2026-10-24-turnos-mapa).
    label: "Turnos y asistencia",
    items: [
      { label: "Mi turno", to: "/my-shift", icon: "⏱", permission: "attendance.clock" },
      { label: "Malla de turnos", to: "/shifts", icon: "▤", permission: ["shifts.manage", "attendance.review"] },
      { label: "Panel de asistencia", to: "/attendance", icon: "◔", permission: "attendance.dashboard" },
      { label: "Novedades y horas", to: "/attendance-review", icon: "✎", permission: "attendance.review" },
      { label: "Nómina", to: "/payroll", icon: "$", permission: "attendance.dashboard" },
      { label: "Mapa operativo", to: "/operations-map", icon: "⌖", permission: ["locations.view", "projects.read_all"] },
    ],
  },
  {
    label: "Bodega",
    items: [
      // Existencias: saldo por artículo y por ubicación, aviso de lo que está en
      // o bajo el mínimo y el botón para cargar el catálogo del Excel. La
      // pantalla la ve quien lea, cuente o administre.
      {
        label: "Existencias",
        to: "/warehouse",
        icon: "⬓",
        permission: ["warehouse.read", "warehouse.manage", "warehouse.count"],
      },
      // El catálogo de artículos (SKU, categoría, unidad, costo, mínimo).
      {
        label: "Artículos",
        to: "/warehouse/items",
        icon: "⬒",
        permission: ["warehouse.read", "warehouse.manage", "warehouse.count"],
      },
      // Las listas predefinidas: lo que cada tipo de trabajo siempre lleva.
      {
        label: "Listas",
        to: "/warehouse/kits",
        icon: "☰",
        permission: ["warehouse.read", "warehouse.kits_manage", "warehouse.manage"],
      },
      // Las órdenes de salida: el técnico las pide y el supervisor las autoriza.
      {
        label: "Salidas",
        to: "/warehouse/releases",
        icon: "⇥",
        permission: ["warehouse.read", "warehouse.request_release", "warehouse.approve_release",
          "warehouse.deliver", "warehouse.manage"],
      },
      // El libro de movimientos: de dónde salió cada cosa y para qué obra.
      {
        label: "Movimientos",
        to: "/warehouse/movements",
        icon: "≡",
        permission: ["warehouse.read", "warehouse.manage", "warehouse.count"],
      },
      // Dónde está cada equipo con serial: en bodega, en una obra o instalado (D-007).
      {
        label: "Seriales",
        to: "/warehouse/serials",
        icon: "#",
        permission: ["warehouse.read", "warehouse.manage", "warehouse.count"],
      },
      // Las compras por adelantado: lo presupuestado por venir menos la existencia.
      {
        label: "Compras sugeridas",
        to: "/warehouse/purchasing",
        icon: "▧",
        permission: ["budgets.manage", "budgets.approve", "warehouse.read"],
      },
      {
        label: "Plantillas de costo",
        to: "/warehouse/cost-templates",
        icon: "◫",
        permission: ["budgets.manage"],
      },
    ],
  },
  {
    label: "Finanzas",
    items: [
      { label: "Facturación y cobros", to: "/invoices", icon: "$", permission: "invoices.read" },
      {
        label: "Gastos de campo",
        to: "/expenses",
        icon: "◇",
        permission: ["expenses.create_own", "expenses.read_all", "expenses.approve"],
      },
      {
        label: "Proveedores y pagos",
        to: "/payables",
        icon: "◫",
        permission: ["payables.manage", "suppliers.manage", "payables.approve"],
      },
      // Banca conectada (como QuickBooks): movimientos de las cuentas y tarjetas de la empresa.
      { label: "Banca", to: "/banking", icon: "▥", permission: "bankfeeds.manage" },
      {
        label: "Conciliación y rentabilidad",
        to: "/finance-close",
        icon: "▤",
        permission: ["reconciliation.manage", "profitability.read"],
      },
    ],
  },
  {
    label: "Administración",
    items: [
      { label: "Reportes", to: "/reports", icon: "▦", permission: "reports.view" },
      {
        label: "Configuración de programas",
        to: "/programs",
        icon: "⚙",
        permission: "programs.manage",
      },
      { label: "Equipo", to: "/users", icon: "♧", permission: "users.manage" },
      { label: "Roles y permisos", to: "/roles", icon: "⚿", permission: "roles.manage" },
      { label: "Auditoría", to: "/audit-log", icon: "◷", permission: "audit.read" },
      {
        label: "Notificaciones",
        to: "/notifications",
        icon: "♢",
        permission: ["notifications.read_own", "notifications.manage"],
      },
    ],
  },
];

/** `true` si el usuario tiene alguno de los permisos que exige la pantalla. */
export function hasAnyPermission(
  permission: string | string[] | undefined,
  user: CurrentUser | null
): boolean {
  if (!user) return false;
  if (!permission) return true; // Sin restricción declarada (Inicio).
  const required = Array.isArray(permission) ? permission : [permission];
  return required.some((code) => user.permissions.includes(code));
}

export function canSee(item: NavItem, user: CurrentUser | null): boolean {
  return hasAnyPermission(item.permission, user);
}

/** Grupos e ítems visibles para este usuario; los grupos vacíos se descartan. */
export function buildNavForUser(user: CurrentUser | null): NavGroup[] {
  if (!user) return [];
  return NAV_GROUPS.map((group) => ({
    label: group.label,
    items: group.items.filter((item) => canSee(item, user)),
  })).filter((group) => group.items.length > 0);
}
