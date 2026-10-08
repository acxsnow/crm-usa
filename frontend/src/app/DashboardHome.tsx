import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { listOverdueTasks } from "@/features/field-ops/api";
import { listCaseActivity, listCasesPage, type CaseActivityItem } from "@/features/cases/api";
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

/** «hace 12 min», «hace 3 h», «hace 2 días». */
function haceCuanto(iso: string): string {
  const segundos = (new Date(iso).getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
  const pasos: [Intl.RelativeTimeFormatUnit, number][] = [["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unidad, s] of pasos) {
    if (Math.abs(segundos) >= s) return rtf.format(Math.round(segundos / s), unidad);
  }
  return "hace un momento";
}

/** Color del avatar según hacia dónde se movió el expediente. */
function colorDeEtapa(stage: string): string {
  if (["approved", "paid", "installed"].includes(stage)) return "green-bg";
  if (["rejected", "closed", "not_interested", "not_eligible"].includes(stage)) return "coral-bg";
  if (["permit_in_progress", "ready_to_install", "inspection_pending", "billing_in_progress"].includes(stage)) return "blue-bg";
  return "purple-bg";
}

function iniciales(nombre: string | null): string {
  if (!nombre) return "SIS";
  return nombre.split(" ").filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");
}

export function DashboardHome() {
  const { user, hasPermission } = useAuth();
  const canSeeTasks = hasPermission("projects.read_all") || hasPermission("projects.read_assigned");
  const canSeeCases =
    hasPermission("cases.read_own") || hasPermission("cases.read_all");
  const canSeeCustomers = hasPermission("customers.read");
  const canSeeFinance = hasPermission("invoices.read");
  // Quien revisa abre el expediente en la revisión; el vendedor, en su formulario.
  const abreRevision = hasPermission("cases.review") || hasPermission("cases.approve") || hasPermission("documents.review");

  // Actividad real (QA-REG-03): los últimos cambios de etapa que este usuario
  // puede ver, sacados del historial del expediente. Antes eran filas fijas.
  const { data: actividad } = useQuery({
    queryKey: ["dashboard-case-activity"],
    queryFn: () => listCaseActivity(8),
    enabled: canSeeCases,
  });

  const accionesRapidas = [
    { show: hasPermission("cases.create"), to: "/sales/visit", icon: "+", color: "coral", title: "Tocar una puerta", hint: "Abre el expediente de una visita" },
    { show: canSeeCases, to: "/cases", icon: "✓", color: "purple", title: "Ver expedientes", hint: "El tablero por etapa" },
    { show: canSeeTasks, to: "/projects", icon: "▣", color: "blue", title: "Ver proyectos", hint: "Instalaciones en curso" },
    { show: canSeeCustomers, to: "/customers", icon: "♙", color: "green", title: "Ver clientes", hint: "Consulta tu cartera" },
  ].filter((a) => a.show);

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
      <div className="page-heading dashboard-heading"><div><p className="eyebrow">{formattedDate.toUpperCase()}</p><h1>Buenos días, {user?.full_name?.split(" ")[0] || "equipo"} <span className="wave">✦</span></h1><p className="page-subtitle">Aquí tienes lo que está pasando hoy en tu operación.</p></div>{hasPermission("cases.create") && <Link className="primary-button" to="/sales/visit">+ Tocar una puerta</Link>}</div>
      <section className="metric-grid" aria-label="Resumen de operación">
        <article className="metric-card"><div className="metric-icon coral">✦</div><div><span>Expedientes activos</span><strong>{activeCases ?? "—"}</strong><small className="neutral">• En prospecto, revisión o aprobados</small></div></article>
        <article className="metric-card"><div className="metric-icon purple">♙</div><div><span>Clientes registrados</span><strong>{customers?.total ?? "—"}</strong><small className="neutral">• Total en tu cartera</small></div></article>
        <article className="metric-card"><div className="metric-icon blue">▣</div><div><span>Proyectos en curso</span><strong>{activeProjects ?? "—"}</strong><small className="neutral">• Planificados, programados o activos</small></div></article>
        <article className="metric-card"><div className="metric-icon green">$</div><div><span>Cobrado este mes</span><strong>{canSeeFinance ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(monthlyCollected) : "—"}</strong><small className="neutral">• Pagos registrados en {monthName}</small></div></article>
      </section>
      <div className="dashboard-columns">
        {canSeeCases && (
          <section className="panel activity-panel">
            <div className="panel-heading">
              <div><h2>Actividad reciente</h2><p>Los últimos movimientos de los expedientes</p></div>
              <Link className="ghost-button" to="/cases">Ver todo →</Link>
            </div>
            <div className="activity-list">
              {actividad && actividad.length === 0 && <p className="page-subtitle">Todavía no hay movimientos.</p>}
              {(actividad ?? []).map((a: CaseActivityItem) => (
                <Link
                  key={`${a.case_id}-${a.occurred_at}-${a.to_stage_code}`}
                  className="activity-item activity-link"
                  to={abreRevision ? `/cases/${a.case_id}/review` : `/cases/${a.case_id}/form`}
                >
                  <span className={`activity-avatar ${colorDeEtapa(a.to_stage_code)}`}>{iniciales(a.actor_name)}</span>
                  <div>
                    <strong>{a.case_number} · {a.label}</strong>
                    <p>{a.customer_name ?? a.address ?? "Sin dirección"} · por {a.actor_name ?? "el sistema"}</p>
                  </div>
                  <time dateTime={a.occurred_at}>{haceCuanto(a.occurred_at)}</time>
                </Link>
              ))}
            </div>
          </section>
        )}
        {accionesRapidas.length > 0 && (
          <section className="panel quick-panel">
            <div className="panel-heading"><div><h2>Acciones rápidas</h2><p>Lo que puedes hacer ahora</p></div></div>
            {accionesRapidas.map((a) => (
              <Link key={a.to} to={a.to} className="quick-action">
                <span className={`quick-icon ${a.color}`}>{a.icon}</span>
                <span><strong>{a.title}</strong><small>{a.hint}</small></span>
                <b>→</b>
              </Link>
            ))}
          </section>
        )}
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
