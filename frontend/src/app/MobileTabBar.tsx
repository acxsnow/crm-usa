import { NavLink } from "react-router-dom";
import type { NavGroup } from "@/config/navigation";
import { Icon, NavIcon } from "@/components/ui/Icon";

/** Destinos de la barra inferior, en orden de prioridad (propuesta UI/UX V1). */
const PRIORIDAD = ["/", "/customers", "/cases", "/my-schedule", "/projects", "/review"];

/**
 * Barra inferior del celular (hasta 767 px): hasta 4 destinos que el usuario
 * puede ver, más «Más», que abre el menú completo. Sale del mismo menú por
 * permiso (`buildNavForUser`), así que no duplica rutas ni muestra lo que el
 * rol no puede abrir.
 */
export function MobileTabBar({ groups, menuOpen, onMore }: {
  groups: NavGroup[];
  menuOpen: boolean;
  onMore: () => void;
}) {
  const visibles = groups.flatMap((g) => g.items).filter((i) => !i.disabled);
  const destinos = PRIORIDAD
    .map((ruta) => visibles.find((i) => i.to === ruta))
    .filter((i): i is (typeof visibles)[number] => Boolean(i))
    .slice(0, 4);

  return (
    <nav className="tabbar" aria-label="Accesos rápidos">
      {destinos.map((i) => (
        <NavLink key={i.to} to={i.to} end={i.to === "/"}
          className={({ isActive }) => (isActive ? "tabbar-item active" : "tabbar-item")}>
          <span className="tabbar-icon" aria-hidden="true"><NavIcon to={i.to} glyph={i.icon} /></span>
          {i.label}
        </NavLink>
      ))}
      <button type="button" className={menuOpen ? "tabbar-item active" : "tabbar-item"}
        aria-controls="menu-principal" aria-expanded={menuOpen} onClick={onMore}>
        <span className="tabbar-icon" aria-hidden="true"><Icon name="menu" /></span>
        Más
      </button>
    </nav>
  );
}
