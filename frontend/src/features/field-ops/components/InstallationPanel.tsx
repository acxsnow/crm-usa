import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const { data: tecnicos } = useInstallers(canSchedule);
  const actual = project.primary_technician_user_id ?? "";
  const [tecnico, setTecnico] = useState(actual);
  const [fecha, setFecha] = useState(project.scheduled_date ?? "");
  // Cambiar el responsable de una obra ya iniciada (el personal rota): el nuevo
  // sigue desde hoy, y la fecha programada original ya pasó y no se acepta.
  const cambiaTecnico = Boolean(actual) && tecnico !== actual;
  function elegirTecnico(id: string) {
    setTecnico(id);
    if (actual && id !== actual && (!fecha || fecha < localISODate())) setFecha(localISODate());
  }

  const schedule = useMutation({
    mutationFn: () => scheduleInstallation(project.id, { technician_user_id: tecnico, scheduled_date: fecha }),
    onSuccess: () => {
      setError(null);
      // El historial de responsables cambia cuando cambia el técnico.
      queryClient.invalidateQueries({ queryKey: ["project-assignments", project.id] });
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
        <select id="orden-tecnico" required value={tecnico} onChange={(e) => elegirTecnico(e.target.value)}>
          <option value="">Elige un técnico</option>
          {(tecnicos ?? []).map((t) => (
            <option key={t.id} value={t.id}>{t.full_name}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="orden-fecha">{cambiaTecnico ? "Sigue desde" : "Fecha de instalación"}</label>
        <input id="orden-fecha" type="date" required min={localISODate()} value={fecha}
          onChange={(e) => setFecha(e.target.value)} />
      </div>
      {cambiaTecnico && (
        <p className="acta-lead" style={{ gridColumn: "1 / -1" }}>
          El nuevo técnico sigue donde el otro terminó. El anterior conserva la obra en solo lectura: ve lo que
          hizo y lo que se va haciendo, pero ya no la llena.
        </p>
      )}
      <button type="submit" className="acta-btn is-primary" disabled={schedule.isPending}>
        {cambiaTecnico ? "Cambiar técnico" : project.scheduled_date ? "Guardar cambio" : "Liberar orden"}
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
