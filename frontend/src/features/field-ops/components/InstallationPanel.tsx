import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiErrorMessage,
  closeInstallation,
  fieldKeys,
  getInstallationGaps,
  getVisitStatus,
  localISODate,
  scheduleInstallation,
  useInstallers,
  useRefreshProject,
  visitKeys,
} from "@/features/field-ops/module5Api";
import { listProjectReleases } from "@/features/warehouse/api";
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
  // Una visita fallida deja la obra sin fecha: el formulario se vacía para que
  // se elija una nueva, en vez de seguir mostrando la vieja (QA del 31 oct).
  useEffect(() => { setFecha(project.scheduled_date ?? ""); }, [project.scheduled_date]);
  useEffect(() => { setTecnico(actual); }, [actual]);
  // Con la orden ya liberada solo se ve el resumen: el formulario se abre con
  // «Cambiar técnico o fecha» (QA del 31 oct: parecía que faltaba liberarla).
  const [editando, setEditando] = useState(false);
  const liberada = Boolean(actual && project.scheduled_date);
  function cancelarCambio() {
    setEditando(false); setTecnico(actual); setFecha(project.scheduled_date ?? ""); setError(null);
  }
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
      setEditando(false);
      // El historial de responsables cambia cuando cambia el técnico.
      queryClient.invalidateQueries({ queryKey: ["project-assignments", project.id] });
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  if (project.status === "cancelled") return null;
  if (!canSchedule || project.status === "completed") {
    return <p className="acta-empty">Solo Administración asigna el técnico y la fecha.</p>;
  }
  return (
    <>
    <ReleaseSummary project={project} technicianName={(tecnicos ?? []).find((t) => t.id === actual)?.full_name} />
    {liberada && !editando ? (
      <div className="acta-actions" style={{ justifyContent: "flex-start", marginBottom: 4 }}>
        <button type="button" className="acta-btn is-small" onClick={() => setEditando(true)}>Cambiar técnico o fecha</button>
      </div>
    ) : (
    <form className="panel-form" onSubmit={(e) => { e.preventDefault(); schedule.mutate(); }}>
      {liberada && (
        <p className="acta-lead" style={{ gridColumn: "1 / -1", margin: 0 }}>
          Cambiar la fecha reagenda la instalación y el técnico la ve en su agenda. Si cambias el técnico, las
          salidas de bodega sin entregar pasan a su nombre.
        </p>
      )}
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
      <div className="acta-actions" style={{ gridColumn: "1 / -1", justifyContent: "flex-start" }}>
        <button type="submit" className="acta-btn is-primary" disabled={schedule.isPending}>
          {schedule.isPending ? "Guardando…" : cambiaTecnico ? "Cambiar técnico" : liberada ? "Guardar cambios" : "Liberar orden"}
        </button>
        {liberada && <button type="button" className="acta-btn is-quiet" onClick={cancelarCambio}>Cancelar</button>}
      </div>
    </form>
    )}
    </>
  );
}

const fechaLarga = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });
const momento = (iso: string) =>
  new Date(iso).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

/**
 * En qué está la orden, en claro (QA de José, 31 oct): quién instala y cuándo,
 * cuándo y quién la liberó, si fue tras una visita fallida y cómo va el
 * material de bodega. Antes solo se veía el formulario y el chulo verde.
 */
function ReleaseSummary({ project, technicianName }: { project: Project; technicianName?: string }) {
  const { data: estado } = useQuery({ queryKey: visitKeys.status(project.id), queryFn: () => getVisitStatus(project.id) });
  const { data: salidas } = useQuery({
    queryKey: ["warehouse-releases", "obra", project.id], queryFn: () => listProjectReleases(project.id), retry: false,
  });
  const vigentes = (salidas ?? []).filter((s) => s.status !== "anulada" && s.status !== "rechazada");
  const entregadas = vigentes.filter((s) => s.status === "entregada");
  const pendientes = vigentes.filter((s) => s.status !== "entregada");
  const liberada = estado?.last_release;

  if (!project.scheduled_date) {
    if (!project.failed_visits_count) return null;
    return (
      <div className="release-summary is-warning" role="status">
        <strong>Sin fecha: la última visita no se pudo hacer.</strong>
        <span>Elige la fecha nueva abajo y toca «Liberar orden» para reagendarla.</span>
      </div>
    );
  }
  return (
    <div className="release-summary" role="status">
      <strong>
        {technicianName ?? "El técnico"} instala el {fechaLarga(project.scheduled_date)}
        {liberada?.after_failed_visit ? " · reagendada después de una visita fallida" : ""}.
      </strong>
      {liberada && <span>Orden liberada el {momento(liberada.at)}{liberada.by_name ? ` por ${liberada.by_name}` : ""}.</span>}
      {salidas && (
        vigentes.length === 0 ? (
          <span className="is-pending">Todavía no tiene material de bodega: pídelo abajo en «Materiales de la orden» para que el técnico lo lleve.</span>
        ) : (
          <span>
            Material de bodega: {[
              entregadas.length ? `${entregadas.length} entregada${entregadas.length > 1 ? "s" : ""}` : null,
              pendientes.length ? `${pendientes.map((s) => s.number ?? "borrador").join(", ")} sin entregar` : null,
            ].filter(Boolean).join(" · ")}.
          </span>
        )
      )}
    </div>
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
