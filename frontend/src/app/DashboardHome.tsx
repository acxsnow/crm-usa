import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { listOverdueTasks } from "@/features/field-ops/api";
import { listCasesPage } from "@/features/cases/api";
import { listCustomersPage } from "@/features/crm/api";
import { listProjectsPage } from "@/features/field-ops/api";
import { listInvoicesPage } from "@/features/billing/api";

async function loadAllPages<T>(fetchPage: (page: number, pageSize: number) => Promise<{ items: T[]; total: number }>): Promise<T[]> {
  const pageSize = 500;
  const firstPage = await fetchPage(1, pageSize);
  const pages = [firstPage.items];
  for (let page = 2; pages.flat().length < firstPage.total; page += 1) {
    const nextPage = await fetchPage(page, pageSize);
    pages.push(nextPage.items);
    if (nextPage.items.length === 0) break;
  }
  return pages.flat();
}

export function DashboardHome() {
  const { user, hasPermission } = useAuth();
  const canSeeTasks = hasPermission("projects.read_all") || hasPermission("projects.read_assigned");
  const canSeeCases =
    hasPermission("cases.read_own") || hasPermission("cases.read_all");
  const canSeeCustomers = hasPermission("customers.read");
  const canSeeFinance = hasPermission("invoices.read");

  // Expedientes que siguen en juego: los que ya abrieron la puerta y todavía
  // no se cerraron. Reemplaza el conteo de prospectos del modelo anterior.
  const { data: activeCases } = useQuery({
    queryKey: ["dashboard-active-cases"],
    queryFn: async () => {
      const etapas = await Promise.all(
        ["new_prospect", "pending_approval", "approved"].map((stage_code) =>
          listCasesPage(1, 1, { stage_code })
        )
      );
      return etapas.reduce((total: number, page) => total + page.total, 0);
    },
    enabled: canSeeCases,
  });
  const { data: customers } = useQuery({
    queryKey: ["dashboard-customers"],
    queryFn: () => listCustomersPage(1, 1),
    enabled: canSeeCustomers,
  });
  const { data: projects } = useQuery({
    queryKey: ["dashboard-projects"],
    queryFn: () => loadAllPages(listProjectsPage),
    enabled: canSeeTasks,
  });
  const { data: invoices } = useQuery({
    queryKey: ["dashboard-invoices"],
    queryFn: () => loadAllPages(listInvoicesPage),
    enabled: canSeeFinance,
  });

  const { data: overdueTasks } = useQuery({
    queryKey: ["overdue-tasks"],
    queryFn: listOverdueTasks,
    enabled: canSeeTasks,
  });

  const currentMonth = new Date().toISOString().slice(0, 7);
  const monthlyCollected = (invoices ?? []).reduce(
    (total, invoice) => total + invoice.payments.filter((payment) => payment.paid_at.slice(0, 7) === currentMonth).reduce((sum, payment) => sum + payment.amount, 0),
    0,
  );
  const activeProjects = projects?.filter((project) => ["planning", "scheduled", "in_progress"].includes(project.status)).length;
  const today = new Date();
  const formattedDate = today.toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const monthName = today.toLocaleDateString("es-CO", { month: "long" });

  return (
    <div className="dashboard-page">
      <div className="page-heading dashboard-heading"><div><p className="eyebrow">{formattedDate.toUpperCase()}</p><h1>Buenos días, {user?.full_name?.split(" ")[0] || "equipo"} <span className="wave">✦</span></h1><p className="page-subtitle">Aquí tienes lo que está pasando hoy en tu operación.</p></div><Link className="primary-button" to="/applications">+ Nuevo expediente</Link></div>
      <section className="metric-grid" aria-label="Resumen de operación">
        <article className="metric-card"><div className="metric-icon coral">✦</div><div><span>Expedientes activos</span><strong>{activeCases ?? "—"}</strong><small className="neutral">• En prospecto, revisión o aprobados</small></div></article>
        <article className="metric-card"><div className="metric-icon purple">♙</div><div><span>Clientes registrados</span><strong>{customers?.total ?? "—"}</strong><small className="neutral">• Total en tu cartera</small></div></article>
        <article className="metric-card"><div className="metric-icon blue">▣</div><div><span>Proyectos en curso</span><strong>{activeProjects ?? "—"}</strong><small className="neutral">• Planificados, programados o activos</small></div></article>
        <article className="metric-card"><div className="metric-icon green">$</div><div><span>Cobrado este mes</span><strong>{canSeeFinance ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(monthlyCollected) : "—"}</strong><small className="neutral">• Pagos registrados en {monthName}</small></div></article>
      </section>
      <div className="dashboard-columns">
        <section className="panel activity-panel"><div className="panel-heading"><div><h2>Actividad reciente</h2><p>El pulso de tu equipo en campo</p></div><button className="ghost-button">Ver todo →</button></div><div className="activity-list"><div className="activity-item"><span className="activity-avatar coral-bg">MC</span><div><strong>María convirtió un prospecto</strong><p>James Wilson · Programa CARE</p></div><time>Hace 12 min</time></div><div className="activity-item"><span className="activity-avatar blue-bg">JR</span><div><strong>Nuevo proyecto creado</strong><p>Instalación · 2847 Mission St.</p></div><time>Hace 38 min</time></div><div className="activity-item"><span className="activity-avatar purple-bg">AL</span><div><strong>Factura marcada como pagada</strong><p>INV-2026-0042 · $2,450.00</p></div><time>Hace 1 h</time></div><div className="activity-item"><span className="activity-avatar green-bg">DP</span><div><strong>Visita de campo completada</strong><p>Robert Chen · San Francisco</p></div><time>Hace 2 h</time></div></div></section>
        <section className="panel quick-panel"><div className="panel-heading"><div><h2>Acciones rápidas</h2><p>Lo que puedes hacer ahora</p></div></div><Link to="/leads" className="quick-action"><span className="quick-icon coral">+</span><span><strong>Agregar prospecto</strong><small>Registra un nuevo contacto</small></span><b>→</b></Link><Link to="/projects" className="quick-action"><span className="quick-icon blue">▣</span><span><strong>Crear proyecto</strong><small>Inicia una nueva instalación</small></span><b>→</b></Link><Link to="/customers" className="quick-action"><span className="quick-icon purple">♙</span><span><strong>Ver clientes</strong><small>Consulta tu cartera</small></span><b>→</b></Link></section>
      </div>

      {canSeeTasks && (
        <div className="overdue-section">
          <div className="panel-heading"><div><h2>Tareas vencidas {overdueTasks && overdueTasks.length > 0 && <span className="status-pill status-inactive">{overdueTasks.length}</span>}</h2><p>Revisa estos pendientes para mantener el ritmo</p></div></div>
          {!overdueTasks || overdueTasks.length === 0 ? (
            <p className="page-subtitle">No hay tareas vencidas — al día.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tarea</th>
                  <th>Proyecto</th>
                  <th>Vencía</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {overdueTasks.map((task) => (
                  <tr key={task.id}>
                    <td>{task.title}</td>
                    <td>{task.project_title}</td>
                    <td>{task.due_date ? new Date(task.due_date).toLocaleDateString() : "—"}</td>
                    <td>
                      <Link className="link-button" to={`/projects/${task.project_id}`}>
                        Ver proyecto
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
