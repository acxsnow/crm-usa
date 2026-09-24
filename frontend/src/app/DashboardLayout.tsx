import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { buildNavForUser } from "@/config/navigation";

export function DashboardLayout() {
  const { user, logout } = useAuth();
  const navGroups = buildNavForUser(user);

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
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
                    <span className="nav-icon">{item.icon}</span>
                    {item.label}
                  </span>
                ) : (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    {item.label}
                  </NavLink>
                )
              )}
            </div>
          ))}
        </nav>
        <div className="sidebar-help"><span className="help-icon">?</span><div><strong>¿Necesitas ayuda?</strong><small>Visita el centro de soporte</small></div></div>
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <div className="topbar-search"><span>⌕</span><input aria-label="Buscar" placeholder="Buscar clientes, proyectos..." /></div>
          <button className="notification-button" aria-label="Notificaciones">♢<i /></button>
          <div className="user-menu">
            <span className="user-avatar">{user?.full_name?.charAt(0).toUpperCase() ?? "U"}</span>
            <div className="user-identity">
              <span className="user-name">{user?.full_name}</span>
              {user?.role_names?.length ? (
                <span className="user-role">{user.role_names.join(" · ")}</span>
              ) : null}
            </div>
          </div>
          <button className="sign-out" onClick={() => logout()}>Salir</button>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
