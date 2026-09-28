import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/AuthContext";
import { listUsers } from "@/features/users/api";
import { apiErrorMessage, listAgenda, localISODate } from "./module5Api";
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
  const semana = thisWeek();
  const [desde, setDesde] = useState(semana.from);
  const [hasta, setHasta] = useState(semana.to);
  const [tecnico, setTecnico] = useState("");

  const { data: users } = useQuery({ queryKey: ["users"], queryFn: listUsers, enabled: esDespacho, retry: false });
  const { data: filas, error, isLoading } = useQuery({
    queryKey: ["dispatch-agenda", desde, hasta, tecnico],
    queryFn: () => listAgenda({ date_from: desde, date_to: hasta, technician_id: tecnico || undefined }),
    enabled: Boolean(desde && hasta),
  });

  const nombre = (id: string | null) => users?.items.find((u) => u.id === id)?.full_name ?? "Sin asignar";
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
                {(users?.items ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
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
                <Link to={`/projects/${fila.project_id}`}>{fila.title}</Link>
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
