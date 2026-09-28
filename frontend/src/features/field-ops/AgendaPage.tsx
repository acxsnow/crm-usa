import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage, listAgenda, localISODate, useInstallers } from "./module5Api";
import type { AgendaRow } from "@/types/fieldOps";

function thisWeek(): { from: string; to: string } {
  const hoy = new Date();
  const lunes = new Date(hoy);
  lunes.setDate(hoy.getDate() - ((hoy.getDay() + 6) % 7));
  const domingo = new Date(lunes);
  domingo.setDate(lunes.getDate() + 6);
  return { from: localISODate(lunes), to: localISODate(domingo) };
}

/**
 * Agenda de instalaciones (spec D5.9). El técnico ve la suya; Administración
 * (`dispatch.manage`) ve la de todos y puede filtrar por técnico. El filtro lo
 * aplica el backend: esconderlo aquí no impediría pedirlo por HTTP.
 */
export function AgendaPage() {
  const { hasPermission } = useAuth();
  const esDespacho = hasPermission("dispatch.manage");
  // Los filtros viven en la dirección de la página: al abrir una orden y
  // pulsar "Volver", la agenda aparece con las mismas fechas y técnico.
  const semana = thisWeek();
  const [params, setParams] = useSearchParams();
  const desde = params.get("desde") ?? semana.from;
  const hasta = params.get("hasta") ?? semana.to;
  const tecnico = params.get("tecnico") ?? "";
  const setFiltro = (clave: string, valor: string) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (valor) next.set(clave, valor); else next.delete(clave);
      return next;
    }, { replace: true });
  const setDesde = (v: string) => setFiltro("desde", v);
  const setHasta = (v: string) => setFiltro("hasta", v);
  const setTecnico = (v: string) => setFiltro("tecnico", v);

  const { data: tecnicos } = useInstallers(esDespacho);
  const { data: filas, error, isLoading } = useQuery({
    queryKey: ["dispatch-agenda", desde, hasta, tecnico],
    queryFn: () => listAgenda({ date_from: desde, date_to: hasta, technician_id: tecnico || undefined }),
    enabled: Boolean(desde && hasta),
  });

  const nombre = (id: string | null) => tecnicos?.find((t) => t.id === id)?.full_name ?? "Sin asignar";
  const porDia = new Map<string, AgendaRow[]>();
  for (const fila of filas ?? []) {
    const dia = fila.scheduled_date ?? "";
    porDia.set(dia, [...(porDia.get(dia) ?? []), fila]);
  }

  return (
    <div className="list-page">
      <div className="page-heading">
        <h1>{esDespacho ? "Agenda de instalaciones" : "Mi agenda"}</h1>
      </div>
      <div className="filter-bar">
        <div className="filter-bar-fields">
          <div className="filter-bar-field">
            <label htmlFor="agenda-desde">Desde</label>
            <input id="agenda-desde" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </div>
          <div className="filter-bar-field">
            <label htmlFor="agenda-hasta">Hasta</label>
            <input id="agenda-hasta" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </div>
          {esDespacho && (
            <div className="filter-bar-field">
              <label htmlFor="agenda-tecnico">Técnico</label>
              <select id="agenda-tecnico" value={tecnico} onChange={(e) => setTecnico(e.target.value)}>
                <option value="">Todos</option>
                {(tecnicos ?? []).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
              </select>
            </div>
          )}
        </div>
      </div>

      {error && <p className="form-error" role="alert">{apiErrorMessage(error, "No se pudo cargar la agenda.")}</p>}
      {isLoading && <p className="loading-state">Cargando…</p>}
      {!isLoading && !error && porDia.size === 0 && <p className="empty-state">No hay instalaciones agendadas en esas fechas.</p>}

      {[...porDia.entries()].map(([dia, lista]) => (
        <section key={dia} className="panel">
          <div className="panel-heading">
            <h3>{new Date(`${dia}T12:00:00`).toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" })}</h3>
          </div>
          <ul className="plain-list">
            {lista.map((fila) => (
              <li key={fila.project_id}>
                <Link to={`/projects/${fila.project_id}`} state={{ backTo: `/my-schedule?${params.toString()}`, backLabel: "Agenda" }}>
                  {fila.title}
                </Link>
                {" · "}
                {[fila.address_street, fila.address_unit, fila.address_city].filter(Boolean).join(", ")}
                {esDespacho && <> · {nombre(fila.primary_technician_user_id)}</>}{" "}
                <span className={`status-pill status-${fila.status}`}>{fila.status === "completed" ? "Cerrada" : "Pendiente"}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
