import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";

const NAV_ITEMS: { to: string; label: string; icon: string; permissions?: string[] }[] = [
  { to: "/", label: "Inicio", icon: "⌂" },
  { to: "/leads", label: "Prospectos", icon: "✦", permissions: ["leads.manage"] },
  { to: "/applications", label: "Aplicaciones", icon: "✓", permissions: ["leads.manage"] },
  { to: "/opportunities", label: "Pipeline", icon: "◈", permissions: ["opportunities.manage"] },
  { to: "/customers", label: "Clientes", icon: "♙", permissions: ["customers.read"] },
  { to: "/projects", label: "Proyectos", icon: "▣", permissions: ["projects.read_all", "projects.read_assigned"] },
  { to: "/technician-monitor", label: "Monitor de técnicos", icon: "◉", permissions: ["dashboards.operations"] },
  { to: "/invoices", label: "Facturación", icon: "$", permissions: ["invoices.read"] },
  { to: "/users", label: "Equipo", icon: "♧", permissions: ["users.manage"] },
  { to: "/audit-log", label: "Actividad", icon: "◷", permissions: ["audit.read"] },
];

export function DashboardLayout() {
  const { user, logout, hasPermission } = useAuth();

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand"><span className="brand-mark">P</span><span>PAP<span className="brand-dot">.</span>CRM</span></div>
        <div className="sidebar-caption">GESTIÓN DE CAMPO</div>
        <nav aria-label="Navegación principal">
          {NAV_ITEMS.filter((item) => !item.permissions || item.permissions.some(hasPermission)).map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              <span className="nav-icon">{item.icon}</span>{item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-help"><span className="help-icon">?</span><div><strong>¿Necesitas ayuda?</strong><small>Visita el centro de soporte</small></div></div>
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <div className="topbar-search"><span>⌕</span><input aria-label="Buscar" placeholder="Buscar clientes, proyectos..." /></div>
          <button className="notification-button" aria-label="Notificaciones">♢<i /></button>
          <div className="user-menu"><span className="user-avatar">{user?.full_name?.charAt(0).toUpperCase() ?? "U"}</span><span className="user-name">{user?.full_name}</span><span className="chevron">⌄</span></div>
          <button className="sign-out" onClick={() => logout()}>Salir</button>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
