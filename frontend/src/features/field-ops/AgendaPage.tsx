import { Link, useSearchParams } from "react-router-dom";

import "../billing/billing.css";
import { PaginationControls } from "@/components/PaginationControls";
import { useAuth } from "@/features/auth/AuthContext";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { localISODate, useInstallers } from "./module5Api";
import type { AgendaRow } from "@/types/fieldOps";

/** `hoy` corrido `dias` días, en formato de fecha local (AAAA-MM-DD). */
function diasDesdeHoy(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return localISODate(d);
}

function diaLargo(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });
}

/** Agrupa filas por fecha de instalación, en el orden en que llegan. */
function porDia(filas: AgendaRow[]): [string, AgendaRow[]][] {
  const grupos = new Map<string, AgendaRow[]>();
  for (const f of filas) {
    const dia = f.scheduled_date ?? "";
    grupos.set(dia, [...(grupos.get(dia) ?? []), f]);
  }
  return [...grupos.entries()];
}

/**
 * Agenda de instalaciones (spec D5.9 y 2026-10-16-agenda-pendientes-historial).
 * Abre con lo que falta por hacer: atrasadas primero (fecha pasada y sin cerrar),
 * hoy y los días que siguen. Lo cerrado vive en «Historial», por páginas. El
 * técnico ve lo suyo; Administración (`dispatch.manage`) ve a todos y filtra por
 * técnico. El servidor aplica los filtros: esconderlos aquí no impediría pedirlos.
 */
export function AgendaPage() {
  const { hasPermission } = useAuth();
  const esDespacho = hasPermission("dispatch.manage");
  // Pestaña y filtros viven en la dirección: al abrir una orden y pulsar
  // "Volver", la agenda aparece igual que como se dejó.
  const [params, setParams] = useSearchParams();
  const historial = params.get("vista") === "historial";
  const hoy = diasDesdeHoy(0);
  const hastaPendiente = params.get("hasta") ?? diasDesdeHoy(14);
  const desdeHistorial = params.get("desde") ?? diasDesdeHoy(-30);
  const hastaHistorial = params.get("hasta") ?? hoy;
  const tecnico = params.get("tecnico") ?? "";
  const setFiltro = (cambios: Record<string, string>) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [clave, valor] of Object.entries(cambios)) {
        if (valor) next.set(clave, valor); else next.delete(clave);
      }
      return next;
    }, { replace: true });
  const cambiarVista = (vista: "" | "historial") => setFiltro({ vista, desde: "", hasta: "" });

  const { data: tecnicos } = useInstallers(esDespacho);
  const lista = usePaginatedQuery<AgendaRow>({
    key: ["dispatch-agenda", historial ? "history" : "pending"],
    path: "/dispatch/agenda",
    pageSize: historial ? 30 : 50,
    params: historial
      ? { view: "history", date_from: desdeHistorial, date_to: hastaHistorial, technician_id: tecnico || undefined }
      : { view: "pending", date_to: hastaPendiente, technician_id: tecnico || undefined },
  });
  const filas = lista.items;
  const nombre = (id: string | null) => tecnicos?.find((t) => t.id === id)?.full_name ?? "Sin asignar";

  const atrasadas = historial ? [] : filas.filter((f) => f.days_late !== null);
  const deHoy = historial ? [] : filas.filter((f) => f.days_late === null && f.scheduled_date === hoy);
  const siguientes = historial ? filas : filas.filter((f) => f.days_late === null && f.scheduled_date !== hoy);

  const orden = (fila: AgendaRow) => (
    <li key={fila.project_id} className={fila.days_late !== null ? "agenda-row-late" : undefined}>
      <Link to={`/projects/${fila.project_id}`} state={{ backTo: `/my-schedule?${params.toString()}`, backLabel: "Agenda" }}>
        {fila.title}
      </Link>
      {" · "}
      {[fila.address_street, fila.address_unit, fila.address_city].filter(Boolean).join(", ")}
      {esDespacho && <> · {nombre(fila.primary_technician_user_id)}</>}{" "}
      {/* Obra de varios días: tiene más de una jornada en el diario. */}
      {fila.day_count > 1 && (
        <span className="status-pill">{fila.day_count} jornadas</span>
      )}{" "}
      {fila.days_late !== null ? (
        <span className="status-pill status-overdue">
          ⏱ {fila.days_late === 1 ? "1 día" : `${fila.days_late} días`} de atraso · {diaLargo(fila.scheduled_date ?? "")}
        </span>
      ) : (
        <span className={`status-pill status-${fila.status}`}>
          {fila.status === "completed" ? "Cerrada" : fila.status === "cancelled" ? "Cancelada" : "Pendiente"}
        </span>
      )}
    </li>
  );

  return (
    <div className="list-page agenda-page">
      <div className="page-heading">
        <h1>{esDespacho ? "Agenda de instalaciones" : "Mi agenda"}</h1>
      </div>

      <nav className="billing-tabs" role="tablist" aria-label="Vista de la agenda">
        <button type="button" role="tab" aria-selected={!historial} className={`billing-tab${!historial ? " is-active" : ""}`}
          onClick={() => cambiarVista("")}>Pendientes</button>
        <button type="button" role="tab" aria-selected={historial} className={`billing-tab${historial ? " is-active" : ""}`}
          onClick={() => cambiarVista("historial")}>Historial</button>
      </nav>

      <div className="filter-bar">
        <div className="filter-bar-fields">
          {historial && (
            <div className="filter-bar-field">
              <label htmlFor="agenda-desde">Desde</label>
              <input id="agenda-desde" type="date" value={desdeHistorial} onChange={(e) => setFiltro({ desde: e.target.value })} />
            </div>
          )}
          <div className="filter-bar-field">
            <label htmlFor="agenda-hasta">{historial ? "Hasta" : "Ver hasta"}</label>
            <input id="agenda-hasta" type="date" value={historial ? hastaHistorial : hastaPendiente}
              min={historial ? undefined : hoy} onChange={(e) => setFiltro({ hasta: e.target.value })} />
          </div>
          {esDespacho && (
            <div className="filter-bar-field">
              <label htmlFor="agenda-tecnico">Técnico</label>
              <select id="agenda-tecnico" value={tecnico} onChange={(e) => setFiltro({ tecnico: e.target.value })}>
                <option value="">Todos</option>
                {(tecnicos ?? []).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
              </select>
            </div>
          )}
        </div>
        {!historial && <p className="agenda-hint">Lo que falta por hacer. Las órdenes atrasadas salen siempre arriba, sin importar la fecha.</p>}
      </div>

      {lista.isLoading && <p className="loading-state">Cargando…</p>}
      {!lista.isLoading && filas.length === 0 && (
        <p className="empty-state">{historial ? "No hay órdenes cerradas en esas fechas." : "Nada pendiente hasta esa fecha. ¡Al día!"}</p>
      )}

      {atrasadas.length > 0 && (
        <section className="panel agenda-late">
          <div className="panel-heading"><h3>Atrasadas · {atrasadas.length}</h3></div>
          <ul className="plain-list">{atrasadas.map(orden)}</ul>
        </section>
      )}
      {deHoy.length > 0 && (
        <section className="panel agenda-today">
          <div className="panel-heading"><h3>Hoy · {diaLargo(hoy)}</h3></div>
          <ul className="plain-list">{deHoy.map(orden)}</ul>
        </section>
      )}
      {porDia(siguientes).map(([dia, grupo]) => (
        <section key={dia} className="panel">
          <div className="panel-heading"><h3>{diaLargo(dia)}</h3></div>
          <ul className="plain-list">{grupo.map(orden)}</ul>
        </section>
      ))}

      <PaginationControls {...lista.controls} />
    </div>
  );
}

