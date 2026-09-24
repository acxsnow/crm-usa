/**
 * Definición del menú y su construcción POR USUARIO.
 *
 * El menú no se escribe dentro del layout: se declara aquí y `buildNavForUser`
 * devuelve solo lo que ese usuario puede ver. Cada ítem se habilita por
 * **módulo** (un grupo de permisos, ver `docs/PERMISOS.md`), no por permisos
 * sueltos: así el menú no tiene que repetir la lógica de agrupamiento que ya
 * vive en el backend y llega en `/auth/me` como `modules`.
 *
 * Los módulos que todavía no existen quedan `disabled: true`: se ven en gris,
 * de modo que el mapa completo del sistema está a la vista desde el principio
 * y quien construya ese módulo solo tiene que quitar la marca.
 */
import type { CurrentUser } from "@/types/auth";

/** Claves de módulo. Coinciden con `MODULES` de `app/shared/permissions.py`. */
export const MODULE = {
  CUSTOMERS: "customers",
  CASES: "cases",
  DOCUMENTS: "documents",
  PROJECTS: "projects",
  DISPATCH: "dispatch",
  PERMITS: "permits",
  BILLING: "billing",
  EXPENSES: "expenses",
  PAYABLES: "payables",
  FINANCE_CLOSE: "finance_close",
  REPORTS: "reports",
  CONFIG: "config",
  TEAM: "team",
  AUDIT: "audit",
  NOTIFICATIONS: "notifications",
} as const;

export interface NavItem {
  label: string;
  to: string;
  icon: string;
  /** Módulo que habilita el ítem. */
  module?: string;
  /**
   * Permiso puntual, cuando el ítem no corresponde al módulo completo.
   * El monitor de técnicos es la vista de supervisión de todo el equipo: si se
   * declarara por el módulo `dispatch`, el técnico lo vería en el menú y
   * recibiría un 403 al entrar, porque su endpoint exige `dashboards.operations`.
   */
  permission?: string;
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
      // Prospectos va por permiso puntual, no por el módulo: el técnico tiene
      // `customers.read` (necesita ver el cliente de su proyecto) pero no
      // `leads.manage`. Declarado por módulo, vería el ítem y recibiría 403.
      { label: "Prospectos", to: "/leads", icon: "✦", permission: "leads.manage" },
      { label: "Clientes", to: "/customers", icon: "♙", module: MODULE.CUSTOMERS },
      { label: "Expedientes", to: "/applications", icon: "✓", module: MODULE.CASES },
      { label: "Pipeline", to: "/opportunities", icon: "◈", module: MODULE.CASES },
      { label: "Documentos", to: "/documents", icon: "🗎", module: MODULE.DOCUMENTS, disabled: true },
    ],
  },
  {
    label: "Operación de campo",
    items: [
      { label: "Proyectos", to: "/projects", icon: "▣", module: MODULE.PROJECTS },
      {
        label: "Monitor de técnicos",
        to: "/technician-monitor",
        icon: "◉",
        permission: "dashboards.operations",
      },
      { label: "Mi agenda", to: "/my-schedule", icon: "◷", permission: "dispatch.read_own", disabled: true },
      { label: "Permisos e inspecciones", to: "/permits", icon: "◪", module: MODULE.PERMITS, disabled: true },
    ],
  },
  {
    label: "Finanzas",
    items: [
      { label: "Facturación y cobros", to: "/invoices", icon: "$", module: MODULE.BILLING },
      { label: "Gastos de campo", to: "/expenses", icon: "◇", module: MODULE.EXPENSES, disabled: true },
      { label: "Proveedores y pagos", to: "/payables", icon: "◫", module: MODULE.PAYABLES, disabled: true },
      {
        label: "Conciliación y rentabilidad",
        to: "/finance-close",
        icon: "▤",
        module: MODULE.FINANCE_CLOSE,
        disabled: true,
      },
    ],
  },
  {
    label: "Administración",
    items: [
      { label: "Reportes", to: "/reports", icon: "▦", module: MODULE.REPORTS, disabled: true },
      { label: "Configuración de programas", to: "/programs", icon: "⚙", module: MODULE.CONFIG, disabled: true },
      { label: "Equipo", to: "/users", icon: "♧", module: MODULE.TEAM },
      { label: "Roles y permisos", to: "/roles", icon: "⚿", permission: "roles.manage" },
      { label: "Auditoría", to: "/audit-log", icon: "◷", module: MODULE.AUDIT },
      { label: "Notificaciones", to: "/notifications", icon: "♢", module: MODULE.NOTIFICATIONS, disabled: true },
    ],
  },
];

export function canSee(item: NavItem, user: CurrentUser | null): boolean {
  if (!user) return false;
  // Sin restricción declarada = visible para cualquiera con sesión (Inicio).
  if (!item.module && !item.permission) return true;
  if (item.permission && user.permissions.includes(item.permission)) return true;
  if (item.module && user.modules.includes(item.module)) return true;
  return false;
}

/** Grupos e ítems visibles para este usuario; los grupos vacíos se descartan. */
export function buildNavForUser(user: CurrentUser | null): NavGroup[] {
  if (!user) return [];
  return NAV_GROUPS.map((group) => ({
    label: group.label,
    items: group.items.filter((item) => canSee(item, user)),
  })).filter((group) => group.items.length > 0);
}
