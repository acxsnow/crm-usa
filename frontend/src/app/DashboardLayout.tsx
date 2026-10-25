import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { NotificationBell } from "@/features/notifications/NotificationBell";
import { GlobalSearch } from "@/features/search/GlobalSearch";
import { useAuth } from "@/features/auth/AuthContext";
import { buildNavForUser } from "@/config/navigation";
import { MobileTabBar } from "./MobileTabBar";
import { NavIcon } from "@/components/ui/Icon";
import { requestLogout, ShiftGate } from "@/features/attendance/ShiftGate";

export function DashboardLayout() {
  const { user, logout } = useAuth();
  const navGroups = buildNavForUser(user);

  // Celular: la barra lateral se vuelve un menú que se abre con ☰ y se cierra
  // al navegar, al tocar fuera o con Escape. En escritorio no cambia nada.
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setMenuOpen(false), [pathname]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <div className="app-shell">
      {menuOpen && <div className="menu-backdrop" aria-hidden="true" onClick={() => setMenuOpen(false)} />}
      <aside id="menu-principal" className={menuOpen ? "app-sidebar is-open" : "app-sidebar"}>
        <button type="button" className="menu-close" aria-label="Cerrar menú" onClick={() => setMenuOpen(false)}>×</button>
        <div className="app-brand"><span className="brand-mark">P</span><span>PAP<span className="brand-dot">.</span>CRM</span></div>
        <div className="sidebar-caption">GESTIÓN DE CAMPO</div>
        <nav aria-label="Navegación principal">
          {navGroups.map((group, index) => (
            <div className="nav-group" key={group.label ?? `group-${index}`}>
              {group.label && <div className="nav-group-label">{group.label}</div>}
              {group.items.map((item) =>
                item.disabled ? (
                  <span
                    key={item.to}
                    className="nav-link disabled"
                    aria-disabled="true"
                    title="Este módulo todavía no está disponible"
                  >
                    <span className="nav-icon"><NavIcon to={item.to} glyph={item.icon} /></span>
                    {item.label}
                  </span>
                ) : (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/warehouse"}
                    className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
                  >
                    <span className="nav-icon"><NavIcon to={item.to} glyph={item.icon} /></span>
                    {item.label}
                  </NavLink>
                )
              )}
            </div>
          ))}
        </nav>
        <div className="menu-account">
          <strong>{user?.full_name}</strong>
          {user?.role_names?.length ? <small>{user.role_names.join(", ")}</small> : null}
          <button type="button" onClick={() => requestLogout(logout)}>Salir</button>
        </div>
        {/* Sin la tarjeta «¿Necesitas ayuda? Visita el centro de soporte»: no
            llevaba a ningún lado (propuesta UI/UX V1: nada de información de relleno). */}
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <button
            type="button"
            className="menu-toggle"
            aria-label="Abrir menú"
            aria-controls="menu-principal"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
          >
            <span aria-hidden="true">☰</span> Menú
          </button>
          <GlobalSearch />
          <NotificationBell />
          <div className="user-menu">
            <span className="user-avatar">{user?.full_name?.charAt(0).toUpperCase() ?? "U"}</span>
            <div className="user-identity">
              <span className="user-name">{user?.full_name}</span>
              {user?.role_names?.length ? (
                <span className="user-role">{user.role_names.join(" · ")}</span>
              ) : null}
            </div>
          </div>
          <button className="sign-out" onClick={() => requestLogout(logout)}>Salir</button>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
      </div>
      {/* Marcación obligatoria y cola sin señal (turnos, spec 2026-10-24). */}
      <ShiftGate />
      <MobileTabBar groups={navGroups} menuOpen={menuOpen} onMore={() => setMenuOpen((v) => !v)} />
    </div>
  );
}
