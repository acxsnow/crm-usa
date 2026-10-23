import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { listOverdueTasksPage } from "@/features/field-ops/api";
import { listCaseActivity, listCasesPage, type CaseActivityItem } from "@/features/cases/api";
import { listCustomersPage } from "@/features/crm/api";
import { listProjectsPage } from "@/features/field-ops/api";
import { getFinanceDashboard } from "@/features/billing/api";
import { KpiCard } from "@/components/ui/KpiCard";

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
  // El tablero de finanzas exige `dashboards.finance`; con `invoices.read` Administración recibía 403 en Inicio.
  const canSeeFinance = hasPermission("dashboards.finance");
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
  const { data: activeCases, isLoading: cargandoExpedientes } = useQuery({
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
  const { data: customers, isLoading: cargandoClientes } = useQuery({
    queryKey: ["dashboard-customers"],
    queryFn: () => listCustomersPage(1, 1),
    enabled: canSeeCustomers,
  });
  // Solo totales: la base cuenta y no se traen listas completas (antes se
  // descargaban todas las páginas de proyectos y facturas para contar).
  const { data: activeProjects, isLoading: cargandoProyectos } = useQuery({
    queryKey: ["dashboard-active-projects"],
    queryFn: async () => {
      const porEstado = await Promise.all(
        ["planning", "scheduled", "in_progress"].map((status) => listProjectsPage(1, 1, { status })));
      return porEstado.reduce((total, page) => total + page.total, 0);
    },
    enabled: canSeeTasks,
  });
  const { data: finanzas, isLoading: cargandoFinanzas } = useQuery({
    queryKey: ["dashboard-finance"],
    queryFn: getFinanceDashboard,
    enabled: canSeeFinance,
  });

  // Las 10 más antiguas y el total; la lista completa vive en Proyectos.
  const { data: vencidas } = useQuery({
    queryKey: ["overdue-tasks", "inicio"],
    queryFn: () => listOverdueTasksPage(1, 10),
    enabled: canSeeTasks,
  });
  const overdueTasks = vencidas?.items;

  const today = new Date();
  const formattedDate = today.toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const monthName = today.toLocaleDateString("es-CO", { month: "long" });

  return (
    <div className="dashboard-page">
      <div className="page-heading dashboard-heading"><div><p className="eyebrow">{formattedDate.charAt(0).toUpperCase() + formattedDate.slice(1)}</p><h1>Buenos días, {user?.full_name?.split(" ")[0] || "equipo"} <span className="wave">✦</span></h1><p className="page-subtitle">Aquí tienes lo que está pasando hoy en tu operación.</p></div>{hasPermission("cases.create") && <Link className="primary-button" to="/sales/visit">+ Tocar una puerta</Link>}</div>
      {/* Solo los indicadores que este rol puede ver: antes salían todos, con «—»
          en los que no tenía permiso (propuesta UI/UX V1: sin datos de relleno). */}
      <section className="metric-grid" aria-label="Resumen de operación">
        {canSeeCases && <KpiCard icon="✓" label="Expedientes activos" value={activeCases ?? "—"} loading={cargandoExpedientes}
          note="En prospecto, revisión o aprobados" to="/cases" />}
        {canSeeCustomers && <KpiCard icon="♙" label="Clientes registrados" value={customers?.total ?? "—"} loading={cargandoClientes}
          note="Total en tu cartera" to="/customers" />}
        {canSeeTasks && <KpiCard icon="▣" label="Proyectos en curso" value={activeProjects ?? "—"} loading={cargandoProyectos}
          note="Planificados, programados o activos" to="/projects" />}
        {canSeeFinance && <KpiCard icon="$" label="Cobrado este mes" loading={cargandoFinanzas}
          value={finanzas ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(finanzas.paid_this_month) : "—"}
          note={`Pagos registrados en ${monthName}`} />}
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
          <div className="panel-heading"><div><h2>Tareas vencidas {vencidas && vencidas.total > 0 && <span className="status-pill status-inactive">{vencidas.total}</span>}</h2><p>Revisa estos pendientes para mantener el ritmo</p></div></div>
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
