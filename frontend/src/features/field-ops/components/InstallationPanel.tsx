import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  apiErrorMessage,
  closeInstallation,
  fieldKeys,
  getInstallationGaps,
  localISODate,
  scheduleInstallation,
  useInstallers,
  useRefreshProject,
} from "@/features/field-ops/module5Api";
import type { Project } from "@/types/fieldOps";
import type { Requirement } from "./InstallationRecord";

/** Paso "Orden liberada": técnico y fecha (spec D5.9). */
export function ReleaseOrderStep({ project, canSchedule }: { project: Project; canSchedule: boolean }) {
  const refresh = useRefreshProject(project.id);
  const [error, setError] = useState<string | null>(null);
  const { data: tecnicos } = useInstallers(canSchedule);
  const [tecnico, setTecnico] = useState(project.primary_technician_user_id ?? "");
  const [fecha, setFecha] = useState(project.scheduled_date ?? "");

  const schedule = useMutation({
    mutationFn: () => scheduleInstallation(project.id, { technician_user_id: tecnico, scheduled_date: fecha }),
    onSuccess: () => {
      setError(null);
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  if (!canSchedule || project.status === "completed") {
    return <p className="acta-empty">Solo Administración asigna el técnico y la fecha.</p>;
  }
  return (
    <form className="panel-form" onSubmit={(e) => { e.preventDefault(); schedule.mutate(); }}>
      {error && <p className="form-error" role="alert" style={{ gridColumn: "1 / -1" }}>{error}</p>}
      <div className="field">
        <label htmlFor="orden-tecnico">Técnico</label>
        <select id="orden-tecnico" required value={tecnico} onChange={(e) => setTecnico(e.target.value)}>
          <option value="">Elige un técnico</option>
          {(tecnicos ?? []).map((t) => (
            <option key={t.id} value={t.id}>{t.full_name}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="orden-fecha">Fecha de instalación</label>
        <input id="orden-fecha" type="date" required min={localISODate()} value={fecha}
          onChange={(e) => setFecha(e.target.value)} />
      </div>
      <button type="submit" className="acta-btn is-primary" disabled={schedule.isPending}>
        {project.scheduled_date ? "Reagendar" : "Liberar orden"}
      </button>
    </form>
  );
}

/**
 * Paso "Cierre": todos los requisitos del cierre, cada uno marcado en verde
 * cuando se cumple, para ver el avance y no solo lo que falta. El botón se
 * habilita cuando el backend confirma que no falta nada.
 */
export function CloseInstallationStep({ project, canClose, requirements }: {
  project: Project; canClose: boolean; requirements: Requirement[];
}) {
  const refresh = useRefreshProject(project.id);
  const [error, setError] = useState<string | null>(null);
  const [observaciones, setObservaciones] = useState("");
  const cerrada = project.status === "completed";
  const { data: gaps } = useQuery({
    queryKey: fieldKeys.gaps(project.id),
    queryFn: () => getInstallationGaps(project.id),
    enabled: !cerrada,
  });

  const close = useMutation({
    mutationFn: () => closeInstallation(project.id, observaciones || undefined),
    onSuccess: () => {
      setError(null);
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  const cumplidos = requirements.filter((r) => r.done).length;
  return (
    <div className="acta-body">
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-requirements">
        <div className="acta-progress">
          <span>{cumplidos} de {requirements.length} requisitos cumplidos</span>
          <span className="acta-progress-bar" aria-hidden="true">
            <span style={{ width: `${requirements.length ? (cumplidos / requirements.length) * 100 : 0}%` }} />
          </span>
        </div>
        <ul>
          {requirements.map((r) => (
            <li key={r.label} className={r.done ? "is-done" : undefined}>
              <span className="acta-tick" aria-hidden="true">{r.done ? "✓" : ""}</span>
              <span>{r.label}</span>
              <span className="visually-hidden">{r.done ? "cumplido" : "pendiente"}</span>
            </li>
          ))}
        </ul>
      </div>
      {cerrada ? (
        <p className="acta-empty">Instalación cerrada. Lo registrado en el acta quedó congelado.</p>
      ) : canClose && (
        <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); close.mutate(); }}>
          <label htmlFor="cierre-observaciones">Observaciones del técnico</label>
          <input id="cierre-observaciones" value={observaciones} onChange={(e) => setObservaciones(e.target.value)}
            placeholder="Cliente conforme, se explicó el uso del termostato" />
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={!gaps?.can_close || close.isPending}>
              {close.isPending ? "Cerrando…" : "Cerrar instalación"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
