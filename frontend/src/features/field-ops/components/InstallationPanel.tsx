import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { listUsers } from "@/features/users/api";
import {
  apiErrorMessage,
  closeInstallation,
  fieldKeys,
  getInstallationGaps,
  localISODate,
  scheduleInstallation,
  useRefreshProject,
} from "@/features/field-ops/module5Api";
import type { Project } from "@/types/fieldOps";

/**
 * Agenda de la orden y cierre de la instalación (spec D5.9).
 *
 * El cierre muestra lo que falta ANTES de intentarlo: el técnico ve la lista
 * en vez de un "no se puede" después de pulsar.
 */
export function InstallationPanel({ project, canSchedule, canClose }: {
  project: Project; canSchedule: boolean; canClose: boolean;
}) {
  const refresh = useRefreshProject(project.id);
  const [error, setError] = useState<string | null>(null);
  const cerrada = project.status === "completed";

  const { data: gaps } = useQuery({
    queryKey: fieldKeys.gaps(project.id),
    queryFn: () => getInstallationGaps(project.id),
    enabled: !cerrada,
  });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: listUsers, enabled: canSchedule, retry: false });

  const [tecnico, setTecnico] = useState(project.primary_technician_user_id ?? "");
  const [fecha, setFecha] = useState(project.scheduled_date ?? "");
  const [observaciones, setObservaciones] = useState("");

  const schedule = useMutation({
    mutationFn: () => scheduleInstallation(project.id, { technician_user_id: tecnico, scheduled_date: fecha }),
    onSuccess: () => {
      setError(null);
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });
  const close = useMutation({
    mutationFn: () => closeInstallation(project.id, observaciones || undefined),
    onSuccess: () => {
      setError(null);
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  return (
    <section className="panel">
      <div className="panel-heading">
        <h3>Instalación</h3>
        {project.scheduled_date && <span className="status-pill status-scheduled">Agendada: {project.scheduled_date}</span>}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}

      {canSchedule && !cerrada && (
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); schedule.mutate(); }}>
          <select aria-label="Técnico" required value={tecnico} onChange={(e) => setTecnico(e.target.value)}>
            <option value="">Técnico…</option>
            {(users?.items ?? []).filter((u) => u.status === "active").map((u) => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </select>
          <input aria-label="Fecha de instalación" type="date" required min={localISODate()}
            value={fecha} onChange={(e) => setFecha(e.target.value)} />
          <button type="submit" disabled={schedule.isPending}>Agendar y liberar orden</button>
        </form>
      )}

      {cerrada ? (
        <p className="info-banner">Instalación cerrada el {project.completed_date}. Lo registrado quedó congelado.</p>
      ) : gaps && !gaps.can_close ? (
        <div className="warning-banner">
          <strong>Para cerrar falta:</strong>
          <ul className="plain-list">{gaps.missing.map((m) => <li key={m}>{m}</li>)}</ul>
        </div>
      ) : null}

      {canClose && !cerrada && (
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); close.mutate(); }}>
          <input aria-label="Observaciones del cierre" placeholder="Observaciones del técnico"
            value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          <button type="submit" className="primary-button" disabled={!gaps?.can_close || close.isPending}>
            {close.isPending ? "Cerrando…" : "Cerrar instalación"}
          </button>
        </form>
      )}
    </section>
  );
}
