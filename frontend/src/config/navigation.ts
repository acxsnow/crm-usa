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
      { label: "Prospectos", to: "/leads", icon: "✦", permission: "leads.manage" },
      // El técnico tiene `customers.read` porque necesita ver el cliente de su
      // proyecto, así que llega hasta aquí — pero no a Prospectos.
      { label: "Clientes", to: "/customers", icon: "♙", permission: "customers.read" },
      {
        label: "Expedientes",
        to: "/applications",
        icon: "✓",
        permission: ["cases.read_own", "cases.read_all"],
      },
      { label: "Pipeline", to: "/opportunities", icon: "◈", permission: "opportunities.manage" },
      {
        label: "Documentos",
        to: "/documents",
        icon: "🗎",
        permission: ["documents.manage", "documents.review"],
        disabled: true,
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
      {
        label: "Mi agenda",
        to: "/my-schedule",
        icon: "◷",
        permission: "dispatch.read_own",
        disabled: true,
      },
      {
        label: "Permisos e inspecciones",
        to: "/permits",
        icon: "◪",
        permission: ["permits.manage", "inspections.manage"],
        disabled: true,
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
        permission: ["expenses.create_own", "expenses.read_all"],
        disabled: true,
      },
      {
        label: "Proveedores y pagos",
        to: "/payables",
        icon: "◫",
        permission: ["payables.manage", "suppliers.manage"],
        disabled: true,
      },
      {
        label: "Conciliación y rentabilidad",
        to: "/finance-close",
        icon: "▤",
        permission: ["reconciliation.manage", "profitability.read"],
        disabled: true,
      },
    ],
  },
  {
    label: "Administración",
    items: [
      { label: "Reportes", to: "/reports", icon: "▦", permission: "reports.view", disabled: true },
      {
        label: "Configuración de programas",
        to: "/programs",
        icon: "⚙",
        permission: "programs.manage",
        disabled: true,
      },
      { label: "Equipo", to: "/users", icon: "♧", permission: "users.manage" },
      { label: "Roles y permisos", to: "/roles", icon: "⚿", permission: "roles.manage" },
      { label: "Auditoría", to: "/audit-log", icon: "◷", permission: "audit.read" },
      {
        label: "Notificaciones",
        to: "/notifications",
        icon: "♢",
        permission: ["notifications.read_own", "notifications.manage"],
        disabled: true,
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
