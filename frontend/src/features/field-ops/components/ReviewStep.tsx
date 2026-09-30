import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  apiErrorMessage,
  confirmTechnicianInfo,
  fieldKeys,
  listReviews,
  returnToTechnician,
  useRefreshProject,
} from "@/features/field-ops/module5Api";
import type { Project } from "@/types/fieldOps";

const ACTION_LABEL = {
  confirmed: "Confirmada por Administración",
  returned: "Devuelta al técnico",
  reopened: "Reabierta por inspección fallida",
} as const;

/**
 * Paso "Confirmación" (módulo 6, spec D6.6): Administración revisa lo que
 * registró el técnico y lo confirma, o se lo devuelve con el motivo. Sin esta
 * confirmación no se crea el cobro.
 */
export function ReviewStep({ project, canReview }: { project: Project; canReview: boolean }) {
  const refresh = useRefreshProject(project.id);
  const { data: historial } = useQuery({ queryKey: fieldKeys.reviews(project.id), queryFn: () => listReviews(project.id) });
  const [error, setError] = useState<string | null>(null);
  const [devolviendo, setDevolviendo] = useState(false);
  const [motivo, setMotivo] = useState("");
  const cerrada = project.status === "completed";

  const done = { onSuccess: () => { setError(null); setDevolviendo(false); setMotivo(""); return refresh(); },
                 onError: (err: unknown) => setError(apiErrorMessage(err)) };
  const confirm = useMutation({ mutationFn: () => confirmTechnicianInfo(project.id), ...done });
  const devolver = useMutation({ mutationFn: () => returnToTechnician(project.id, motivo), ...done });

  return (
    <div className="acta-body">
      {error && <p className="form-error" role="alert">{error}</p>}
      {project.technician_info_confirmed ? (
        <p className="acta-empty">Información técnica confirmada. Ya se puede crear el cobro.</p>
      ) : !cerrada ? (
        <p className="acta-empty">
          {project.returned_reason
            ? "El acta está devuelta al técnico; se confirma cuando la vuelva a cerrar."
            : "Se confirma cuando el técnico cierre el acta."}
        </p>
      ) : canReview ? (
        <>
          <p className="acta-lead">
            Revisa fotos, seriales y checklist. Si algo está mal, devuélvela al técnico con lo que debe corregir.
          </p>
          {!devolviendo ? (
            <div className="acta-actions" style={{ justifyContent: "flex-start" }}>
              <button type="button" className="acta-btn is-primary" disabled={confirm.isPending}
                onClick={() => confirm.mutate()}>
                {confirm.isPending ? "Confirmando…" : "Confirmar información técnica"}
              </button>
              <button type="button" className="acta-btn" onClick={() => setDevolviendo(true)}>
                Devolver al técnico
              </button>
            </div>
          ) : (
            <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); devolver.mutate(); }}>
              <label htmlFor="devolver-motivo">Qué debe corregir el técnico</label>
              <input id="devolver-motivo" required minLength={3} value={motivo} autoFocus
                onChange={(e) => setMotivo(e.target.value)} placeholder="La foto de la etiqueta exterior no se lee" />
              <div className="acta-actions">
                <button type="submit" className="acta-btn is-primary" disabled={devolver.isPending}>Devolver</button>
                <button type="button" className="acta-btn is-quiet" onClick={() => setDevolviendo(false)}>Cancelar</button>
              </div>
            </form>
          )}
        </>
      ) : (
        <p className="acta-empty">Pendiente de que Administración confirme la información.</p>
      )}

      {(historial ?? []).length > 0 && (
        <>
          <h4 className="acta-section-title">Historial</h4>
          <ul className="acta-history">
            {(historial ?? []).map((r) => (
              <li key={r.id} className={`is-${r.action}`}>
                <strong>{ACTION_LABEL[r.action]}</strong>
                <span>{new Date(r.created_at).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" })}</span>
                {r.reason && <p>{r.reason}</p>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
