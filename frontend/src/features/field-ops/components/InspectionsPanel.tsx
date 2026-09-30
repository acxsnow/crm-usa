import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  apiErrorMessage,
  fieldKeys,
  listInspections,
  recordInspectionResult,
  scheduleInspection,
  uploadSignedPermit,
  useFieldCatalogs,
  useRefreshProject,
} from "@/features/field-ops/module5Api";
import type { Inspection } from "@/types/fieldOps";

/**
 * Inspección municipal con intentos (spec D5.6). Se agenda con la instalación
 * cerrada; una fallida devuelve la orden a campo y el intento queda aquí.
 */
export function InspectionsPanel({ projectId, canManage, installationClosed }: {
  projectId: string; canManage: boolean; installationClosed: boolean;
}) {
  const { data: catalogs } = useFieldCatalogs();
  const { data: intentos } = useQuery({ queryKey: fieldKeys.inspections(projectId), queryFn: () => listInspections(projectId) });
  const refresh = useRefreshProject(projectId);
  const [cuando, setCuando] = useState("");
  const [inspector, setInspector] = useState("");
  const [error, setError] = useState<string | null>(null);
  const hayPendiente = (intentos ?? []).some((i) => i.result === "pending");
  // Con la última aprobada no hay nada más que agendar.
  const aprobada = (intentos ?? [])[(intentos ?? []).length - 1]?.result === "passed";

  const schedule = useMutation({
    mutationFn: () => scheduleInspection(projectId, {
      scheduled_for: new Date(cuando).toISOString(), inspector_name: inspector || undefined,
    }),
    onSuccess: () => {
      setError(null);
      setCuando("");
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  return (
    <div className="acta-body">
      {error && <p className="form-error" role="alert">{error}</p>}
      {(intentos ?? []).length === 0 && <p className="acta-empty">Sin inspecciones.</p>}
      <ol className="plain-list">
        {(intentos ?? []).map((i, n) => (
          <InspectionRow key={i.id} inspection={i} attempt={n + 1}
            resultLabel={catalogs?.inspection_results[i.result] ?? i.result}
            canManage={canManage} onError={setError} onChanged={refresh} />
        ))}
      </ol>
      {canManage && installationClosed && !hayPendiente && !aprobada && (
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); schedule.mutate(); }}>
          <input aria-label="Fecha y hora de la inspección" type="datetime-local" required
            value={cuando} onChange={(e) => setCuando(e.target.value)} />
          <input aria-label="Inspector o entidad" placeholder="Inspector o entidad"
            value={inspector} onChange={(e) => setInspector(e.target.value)} />
          <button type="submit" disabled={schedule.isPending}>Agendar inspección</button>
        </form>
      )}
      {canManage && !installationClosed && (
        <p className="info-banner">La inspección se agenda cuando la instalación esté cerrada.</p>
      )}
    </div>
  );
}

function InspectionRow({ inspection, attempt, resultLabel, canManage, onError, onChanged }: {
  inspection: Inspection; attempt: number; resultLabel: string; canManage: boolean;
  onError: (m: string) => void; onChanged: () => Promise<unknown>;
}) {
  const [observaciones, setObservaciones] = useState("");
  const [permisoSubido, setPermisoSubido] = useState<string | null>(null);
  const upload = useMutation({
    mutationFn: (file: File) => uploadSignedPermit(inspection.id, file),
    onSuccess: (_, file) => {
      setPermisoSubido(file.name);
      return onChanged();
    },
    onError: (err) => onError(apiErrorMessage(err)),
  });
  const record = useMutation({
    mutationFn: (result: "passed" | "failed") =>
      recordInspectionResult(inspection.id, { result, observations: observaciones || undefined }),
    onSuccess: onChanged,
    onError: (err) => onError(apiErrorMessage(err)),
  });
  const estilo = inspection.result === "passed" ? "status-completed" : inspection.result === "failed" ? "status-overdue" : "status-pending";

  return (
    <li>
      <strong>Intento {attempt}</strong> · {new Date(inspection.scheduled_for).toLocaleString("es-CO")}
      {inspection.inspector_name ? ` · ${inspection.inspector_name}` : ""}{" "}
      <span className={`status-pill ${estilo}`}>{resultLabel}</span>
      {inspection.observations && <p className="page-subtitle">{inspection.observations}</p>}
      {canManage && inspection.result === "pending" && (
        <div className="acta-signed-permit">
          <label className="acta-btn is-line">
            <input type="file" accept="image/*,application/pdf" className="visually-hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
            {upload.isPending ? "Subiendo…" : permisoSubido ? "Cambiar permiso firmado" : "Subir permiso firmado por el inspector"}
          </label>
          <span className="acta-empty">
            {permisoSubido ? `✓ ${permisoSubido}` : "Sin la firma del inspector en el permiso no se aprueba ni se cobra."}
          </span>
        </div>
      )}
      {canManage && inspection.result === "pending" && (
        <div className="inline-form">
          <input aria-label="Observaciones del inspector" placeholder="Observaciones (obligatorias si falla)"
            value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          <button type="button" disabled={record.isPending} onClick={() => record.mutate("passed")}>Aprobada</button>
          <button type="button" className="ghost-button" disabled={record.isPending} onClick={() => record.mutate("failed")}>
            Fallida
          </button>
        </div>
      )}
    </li>
  );
}
