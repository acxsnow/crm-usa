import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { listPrograms } from "@/features/programs/api";
import { decideProgram, getCaseProgramsDetail, setAdditionalPrograms, type CaseProgramDetail } from "./api";

const ESTADO: Record<CaseProgramDetail["status"], { texto: string; clase: string }> = {
  pending: { texto: "Pendiente", clase: "is-preparing" },
  approved: { texto: "Aprobado", clase: "is-paid" },
  rejected: { texto: "Rechazado", clase: "is-rejected" },
};
const SIN_DECISION = ["no_contact", "not_interested", "not_eligible", "new_prospect"];
const TERMINADO = ["paid", "closed", "rejected"];

/**
 * Los programas del expediente (cliente, 28 nov 2026): una misma instalación
 * puede ir a varios programas. El formulario se llena una vez y una firma vale
 * para todos; cada programa se aprueba aparte y solo se cobra a los aprobados.
 */
export function CasePrograms({ caseId, stage, canEdit, canDecide, onDone }: {
  caseId: string; stage: string; canEdit: boolean; canDecide: boolean; onDone?: () => void;
}) {
  const queryClient = useQueryClient();
  const clave = ["case-programs-detail", caseId];
  const { data: lista = [] } = useQuery({ queryKey: clave, queryFn: () => getCaseProgramsDetail(caseId) });
  const puedeEditar = canEdit && !TERMINADO.includes(stage) && lista.length > 0;
  const { data: todos } = useQuery({ queryKey: ["board-programs"], queryFn: listPrograms, staleTime: 5 * 60 * 1000,
    enabled: puedeEditar });
  const [nuevo, setNuevo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const listo = (programs: CaseProgramDetail[]) => {
    setError(null);
    queryClient.setQueryData(clave, programs);
    queryClient.invalidateQueries({ queryKey: ["case-programs", caseId] });
    onDone?.();
  };
  const adicionales = lista.filter((p) => !p.is_primary).map((p) => p.program_id);
  const cambiar = useMutation({
    mutationFn: (ids: string[]) => setAdditionalPrograms(caseId, ids),
    onSuccess: (programs) => { setNuevo(""); listo(programs); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  if (lista.length === 0) return null;
  const disponibles = (todos ?? []).filter((p) => p.active && !lista.some((x) => x.program_id === p.id));
  return (
    <section className="review-section case-programs" aria-labelledby="case-programs">
      <h2 id="case-programs">{lista.length > 1 ? "Programas" : "Programa"}</h2>
      {lista.length > 1 && (
        <p className="acta-note">El formulario y la firma valen para todos. Cada programa se aprueba aparte y solo se le
          cobra a los aprobados.</p>
      )}
      <ul className="case-program-list">
        {lista.map((p) => (
          <ProgramaFila key={p.program_id} caseId={caseId} p={p}
            canDecide={canDecide && !p.is_primary && !SIN_DECISION.includes(stage)}
            onQuitar={puedeEditar && !p.is_primary
              ? () => cambiar.mutate(adicionales.filter((id) => id !== p.program_id)) : undefined}
            onDone={listo} />
        ))}
      </ul>
      {puedeEditar && disponibles.length > 0 && (
        <div className="imp-program-row">
          <select aria-label="Agregar programa" value={nuevo} onChange={(e) => setNuevo(e.target.value)}>
            <option value="">Agregar otro programa…</option>
            {disponibles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <button type="button" className="acta-btn" disabled={!nuevo || cambiar.isPending}
            onClick={() => cambiar.mutate([...adicionales, nuevo])}>Agregar</button>
        </div>
      )}
      {error && <p className="form-error-text" role="alert">{error}</p>}
    </section>
  );
}

function ProgramaFila({ caseId, p, canDecide, onQuitar, onDone }: {
  caseId: string; p: CaseProgramDetail; canDecide: boolean; onQuitar?: () => void;
  onDone: (programs: CaseProgramDetail[]) => void;
}) {
  const [accion, setAccion] = useState<"approved" | "rejected" | null>(null);
  const [texto, setTexto] = useState("");
  const [error, setError] = useState<string | null>(null);
  const decidir = useMutation({
    mutationFn: () => decideProgram(caseId, p.program_id, accion === "approved"
      ? { decision: "approved", approval_code: texto } : { decision: "rejected", reason: texto }),
    onSuccess: (programs) => { setAccion(null); setTexto(""); setError(null); onDone(programs); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const estado = ESTADO[p.status];
  return (
    <li className="case-program-item">
      <div className="case-program-head">
        <strong>{p.name}</strong>
        <span className="billing-chip">{p.is_primary ? "Principal" : "Adicional"}</span>
        <span className={`billing-chip ${estado.clase}`}>{estado.texto}</span>
        {p.approval_code && <span className="acta-data">Código {p.approval_code}</span>}
      </div>
      {p.decision_reason && p.status === "rejected" && <p className="acta-note">Motivo: {p.decision_reason}</p>}
      {p.missing.length > 0 && <p className="acta-note">A este programa le falta: {p.missing.join("; ")}.</p>}
      {(canDecide || onQuitar) && !accion && (
        <div className="case-program-actions">
          {canDecide && p.status !== "approved" && (
            <button type="button" className="acta-btn is-primary" onClick={() => setAccion("approved")}>Aprobar</button>
          )}
          {canDecide && p.status !== "rejected" && (
            <button type="button" className="acta-btn is-quiet" onClick={() => setAccion("rejected")}>Rechazar</button>
          )}
          {onQuitar && <button type="button" className="link-button" onClick={onQuitar}>Quitar</button>}
        </div>
      )}
      {accion && (
        <form className="imp-program-row" onSubmit={(e) => { e.preventDefault(); decidir.mutate(); }}>
          <input aria-label={accion === "approved" ? "Código de aprobación" : "Motivo del rechazo"} autoFocus
            placeholder={accion === "approved" ? "Código de aprobación (opcional)" : "Motivo del rechazo"}
            value={texto} onChange={(e) => setTexto(e.target.value)} required={accion === "rejected"} />
          <button type="submit" className="acta-btn is-primary" disabled={decidir.isPending}>
            {accion === "approved" ? "Aprobar" : "Rechazar"}
          </button>
          <button type="button" className="link-button" onClick={() => { setAccion(null); setTexto(""); }}>Cancelar</button>
        </form>
      )}
      {error && <p className="form-error-text" role="alert">{error}</p>}
    </li>
  );
}
