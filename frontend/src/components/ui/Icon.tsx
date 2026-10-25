import type { ReactNode } from "react";

/**
 * Íconos de línea (trazo 1.75, 24 px) de la propuesta UI/UX V1. Dibujados a
 * mano para no sumar una librería; cada uno es un `<svg>` decorativo
 * (`aria-hidden`): el texto que lo acompaña es el que se lee.
 */
const TRAZOS: Record<string, ReactNode> = {
  home: <><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /><path d="M10 21v-6h4v6" /></>,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6" /><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8" /><path d="M18 14.3c2.1.7 3.5 2.8 3.5 5.7" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  megaphone: <><path d="M3 10v4a1 1 0 0 0 1 1h3l6 4V5L7 9H4a1 1 0 0 0-1 1Z" /><path d="M17 8.5a5 5 0 0 1 0 7" /><path d="M19.5 6a8.5 8.5 0 0 1 0 12" /></>,
  folder: <><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5Z" /></>,
  inbox: <><path d="M3 13.5 5.5 5h13l2.5 8.5V19a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z" /><path d="M3 13.5h5l1.5 2.5h5l1.5-2.5h5" /></>,
  briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8.5 7V5a1.5 1.5 0 0 1 1.5-1.5h4A1.5 1.5 0 0 1 15.5 5v2" /><path d="M3 12.5h18" /></>,
  radar: <><circle cx="12" cy="10" r="3" /><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11Z" /></>,
  calendar: <><rect x="3" y="4.5" width="18" height="16" rx="2" /><path d="M3 9.5h18M8 2.5v4M16 2.5v4" /></>,
  checklist: <><path d="M10 6h10M10 12h10M10 18h10" /><path d="m3.5 6 1.5 1.5L7.5 5M3.5 12l1.5 1.5 2.5-2.5M3.5 18l1.5 1.5 2.5-2.5" /></>,
  shield: <><path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.2 7.5 9.5 4.3-1.3 7.5-4.9 7.5-9.5V6Z" /><path d="m9 12 2 2 4-4" /></>,
  box: <><path d="m3.5 7.5 8.5-4.5 8.5 4.5v9L12 21l-8.5-4.5Z" /><path d="m3.5 7.5 8.5 4.5 8.5-4.5M12 12v9" /></>,
  tag: <><path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9Z" /><circle cx="7.5" cy="7.5" r="1.5" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5Z" /><path d="m3 13 9 5 9-5" /></>,
  truck: <><path d="M2.5 6.5h11v10h-11Z" /><path d="M13.5 9.5h4l3 3.5v3.5h-7" /><circle cx="6.5" cy="17.5" r="1.8" /><circle cx="17" cy="17.5" r="1.8" /></>,
  arrows: <><path d="M4 8h14l-3.5-3.5M20 16H6l3.5 3.5" /></>,
  cart: <><circle cx="9" cy="20" r="1.4" /><circle cx="18" cy="20" r="1.4" /><path d="M2.5 3.5h3l2.4 11.2a1.5 1.5 0 0 0 1.5 1.3h8.3a1.5 1.5 0 0 0 1.5-1.2L21 7.5H6.4" /></>,
  calculator: <><rect x="4.5" y="2.5" width="15" height="19" rx="2" /><path d="M8 6.5h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15v3M8 18h4" /></>,
  receipt: <><path d="M5 2.5h14v19l-2.5-1.5-2.3 1.5-2.2-1.5-2.3 1.5L7.5 20 5 21.5Z" /><path d="M8.5 7.5h7M8.5 11.5h7M8.5 15.5h4" /></>,
  wallet: <><path d="M3.5 7a2 2 0 0 1 2-2H18v4" /><rect x="3.5" y="7" width="17" height="13" rx="2" /><path d="M16 13.5h.01" /></>,
  card: <><rect x="2.5" y="5" width="19" height="14" rx="2" /><path d="M2.5 10h19M6.5 15h4" /></>,
  lock: <><rect x="4.5" y="10.5" width="15" height="10.5" rx="2" /><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" /></>,
  chart: <><path d="M3.5 3.5v17h17" /><path d="M8 16v-4M12.5 16V8M17 16v-6.5" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></>,
  team: <><circle cx="12" cy="7.5" r="3.5" /><path d="M5 20.5c0-3.9 3.1-6.5 7-6.5s7 2.6 7 6.5" /></>,
  key: <><circle cx="8" cy="15" r="4.5" /><path d="m11.2 11.8 8.3-8.3M16.5 6.5l2.5 2.5M14.5 8.5l2 2" /></>,
  history: <><path d="M3.5 12a8.5 8.5 0 1 0 2.5-6" /><path d="M3.5 4.5V9H8" /><path d="M12 8v4.5l3 2" /></>,
  bell: <><path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9Z" /><path d="M10 20a2.2 2.2 0 0 0 4 0" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.4-4.4" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3.5 6.5 8.5 6 8.5-6" /></>,
  phone: <><path d="M5 3.5h3.5l1.8 4.5-2.3 1.4a11 11 0 0 0 6.6 6.6l1.4-2.3 4.5 1.8V19a1.5 1.5 0 0 1-1.6 1.5A16.5 16.5 0 0 1 3.5 5.1 1.5 1.5 0 0 1 5 3.5Z" /></>,
  pin: <><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11Z" /><circle cx="12" cy="10" r="2.5" /></>,
  note: <><path d="M5 3.5h10l4 4v13H5Z" /><path d="M14.5 3.5v4.5H19M8.5 12.5h7M8.5 16.5h5" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4.5 21c0-4.1 3.4-7 7.5-7s7.5 2.9 7.5 7" /></>,
  door: <><path d="M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17" /><path d="M3 21h18M14.5 12h.01" /></>,
  chevronLeft: <><path d="m15 5-7 7 7 7" /></>,
  chevronRight: <><path d="m9 5 7 7-7 7" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  grid: <><rect x="3.5" y="4.5" width="17" height="15" rx="2" /><path d="M3.5 9.5h17M9 9.5v10M14.5 9.5v10" /></>,
  gauge: <><path d="M4 16a8 8 0 1 1 16 0" /><path d="m12 16 3.5-4.5" /><path d="M4 16h2M18 16h2" /></>,
  edit: <><path d="M4 20h4L19 9l-4-4L4 16Z" /><path d="m13.5 6.5 4 4" /></>,
  dollar: <><path d="M12 3v18" /><path d="M16.5 7.5c0-1.7-2-3-4.5-3s-4.5 1.3-4.5 3 2 2.6 4.5 3 4.5 1.4 4.5 3.2-2 3-4.5 3-4.5-1.3-4.5-3" /></>,
  bank: <><path d="M3 9.5 12 4l9 5.5" /><path d="M4.5 10v8M9.5 10v8M14.5 10v8M19.5 10v8M3 20.5h18" /></>,
  map: <><path d="m3.5 6.5 5.5-2 6 2 5.5-2v13l-5.5 2-6-2-5.5 2Z" /><path d="M9 4.5v13M15 6.5v13" /></>,
};

export type IconName = keyof typeof TRAZOS;

/** Ícono por ruta del menú. Sin entrada, el menú usa el glifo de `navigation.ts`. */
export const ICONO_DE_RUTA: Record<string, IconName> = {
  "/": "home",
  "/customers": "users",
  "/sales": "sun",
  "/campaigns": "megaphone",
  "/cases": "folder",
  "/review": "inbox",
  "/projects": "briefcase",
  "/technician-monitor": "radar",
  "/my-schedule": "calendar",
  "/works-calendar": "layers",
  "/checklists": "checklist",
  "/permits": "shield",
  "/warehouse": "box",
  "/warehouse/items": "tag",
  "/warehouse/kits": "layers",
  "/warehouse/releases": "truck",
  "/warehouse/movements": "arrows",
  "/warehouse/purchasing": "cart",
  "/warehouse/cost-templates": "calculator",
  "/invoices": "receipt",
  "/expenses": "wallet",
  "/payables": "card",
  "/finance-close": "lock",
  "/reports": "chart",
  "/programs": "settings",
  "/users": "team",
  "/roles": "key",
  "/audit-log": "history",
  "/notifications": "bell",
  "/my-shift": "clock",
  "/shifts": "grid",
  "/attendance": "gauge",
  "/attendance-review": "edit",
  "/payroll": "dollar",
  "/operations-map": "map",
  "/banking": "bank",
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg className="ui-icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {TRAZOS[name]}
    </svg>
  );
}

/** El ícono de una entrada del menú: de línea si la ruta tiene uno, si no el glifo de siempre. */
export function NavIcon({ to, glyph }: { to: string; glyph: string }) {
  const nombre = ICONO_DE_RUTA[to];
  return nombre ? <Icon name={nombre} /> : <>{glyph}</>;
}
