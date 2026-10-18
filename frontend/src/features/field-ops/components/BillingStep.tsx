import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  billingKeys,
  createClaim,
  getEligibility,
  listClaims,
  money,
  openInvoicePreview,
  shortDay,
  useRefreshBilling,
} from "@/features/billing/billingApi";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { CLAIM_STATUS_LABELS, type EligibleProgram } from "@/types/billing";
import type { Project } from "@/types/fieldOps";

/**
 * Paso "Cobro" del acta (módulo 6): qué programas aplican a la dirección en la
 * fecha de la instalación, los cobros que ya existen y crear los que faltan.
 * El seguimiento (checklist, radicar, pago) va en el detalle del cobro.
 */
export function BillingStep({ project, canCreate, canRead }: {
  project: Project; canCreate: boolean; canRead: boolean;
}) {
  const { data: elegibilidad, error: errorElegibilidad } = useQuery({
    queryKey: billingKeys.eligibility(project.id), queryFn: () => getEligibility(project.id), enabled: canRead,
  });
  const { data: cobros } = useQuery({
    queryKey: billingKeys.projectClaims(project.id), queryFn: () => listClaims({ project_id: project.id }),
    enabled: canRead,
  });

  if (!canRead) return <p className="acta-empty">El cobro lo gestionan Administración y Contabilidad.</p>;
  if (errorElegibilidad) return <p className="form-error">{apiErrorMessage(errorElegibilidad)}</p>;
  if (!elegibilidad) return <p className="acta-empty">Cargando programas…</p>;

  const vivos = (cobros ?? []).filter((c) => c.status !== "withdrawn");
  const sinCobro = elegibilidad.programs.filter((p) => !p.claim_id);

  return (
    <div className="acta-body">
      <p className="acta-lead">
        {elegibilidad.installation_date
          ? <>Programas según la dirección el <strong>{shortDay(elegibilidad.installation_date)}</strong> (fecha de la instalación). La tarifa es la vigente ese día.</>
          : "La instalación aún no está cerrada: se muestran los programas de hoy."}
      </p>

      {vivos.length > 0 && (
        <>
          <h4 className="acta-section-title">Cobros de esta instalación</h4>
          <ul className="billing-claim-list">
            {vivos.map((c) => (
              <li key={c.id}>
                <Link to={`/invoices/claims/${c.id}`} className="billing-claim-row">
                  <span className="billing-claim-program">{c.program_name}</span>
                  <span className="billing-amount">{money(c.amount)}</span>
                  <span className={`billing-chip is-${c.status}`}>{CLAIM_STATUS_LABELS[c.status]}</span>
                  <span className="billing-claim-go" aria-hidden="true">›</span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      {sinCobro.length > 0 && (
        <>
          <h4 className="acta-section-title">{vivos.length ? "Otros programas" : "Programas"}</h4>
          <ul className="billing-claim-list">
            {sinCobro.map((p) => (
              <ProgramRow key={p.program_id} project={project} program={p}
                canCreate={canCreate && elegibilidad.technician_info_confirmed} />
            ))}
          </ul>
        </>
      )}
      {elegibilidad.programs.length === 0 && (
        <p className="acta-empty">No hay programas activos. Configúralos en Facturación › Programas.</p>
      )}
      {canCreate && !elegibilidad.technician_info_confirmed && (
        <p className="info-banner">El cobro se crea cuando Administración confirme la información técnica.</p>
      )}
    </div>
  );
}

function ProgramRow({ project, program, canCreate }: { project: Project; program: EligibleProgram; canCreate: boolean }) {
  const refresh = useRefreshBilling();
  const [error, setError] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");
  const [pidiendoMotivo, setPidiendoMotivo] = useState(false);
  const crear = useMutation({
    mutationFn: () => createClaim(project.id, program.program_id, motivo || undefined),
    onSuccess: () => { setError(null); setPidiendoMotivo(false); return refresh(project.id); },
    onError: (err) => setError(apiErrorMessage(err)),
  });
  const preview = useMutation({
    mutationFn: () => openInvoicePreview({ kind: "rebate", project_id: project.id, program_id: program.program_id }),
    onError: (err) => setError(apiErrorMessage(err)),
    meta: { silent: true },  // abre la vista previa, no guarda
  });

  return (
    <li className={`billing-program ${program.applies ? "is-applies" : "is-out"}`}>
      <div className="billing-program-head">
        <div>
          <strong>{program.program_name}</strong>
          <span className="billing-program-why">
            {program.applies ? `Aplica: ${program.jurisdiction_label}` : "No está en la zona del programa"}
          </span>
        </div>
        <span className="billing-amount">{program.rate != null ? money(program.rate) : "Sin tarifa"}</span>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {canCreate && program.rate != null && !pidiendoMotivo && (
        <div className="acta-actions" style={{ justifyContent: "flex-start" }}>
          <button type="button" className={`acta-btn ${program.applies ? "is-primary" : ""}`} disabled={crear.isPending}
            onClick={() => (program.applies ? crear.mutate() : setPidiendoMotivo(true))}>
            {crear.isPending ? "Creando…" : "Crear cobro"}
          </button>
          <button type="button" className="acta-btn is-quiet" disabled={preview.isPending} onClick={() => preview.mutate()}>
            Vista previa de la factura
          </button>
        </div>
      )}
      {pidiendoMotivo && (
        <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
          <label htmlFor={`motivo-${program.program_id}`}>¿Por qué se cobra aunque no esté en la zona?</label>
          <input id={`motivo-${program.program_id}`} required minLength={3} value={motivo} autoFocus
            onChange={(e) => setMotivo(e.target.value)} placeholder="El programa aceptó el caso por excepción" />
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={crear.isPending}>Crear cobro</button>
            <button type="button" className="acta-btn is-quiet" onClick={() => setPidiendoMotivo(false)}>Cancelar</button>
          </div>
        </form>
      )}
    </li>
  );
}
