import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import "./billing.css";
import { useAuth } from "@/features/auth/AuthContext";
import { ActaSteps, type RecordStep, type StepState } from "@/features/field-ops/components/InstallationRecord";
import { apiErrorMessage, localISODate } from "@/features/field-ops/module5Api";
import { CLAIM_STATUS_LABELS, REJECTION_CATEGORIES, type ClaimDetail } from "@/types/billing";
import {
  billingKeys,
  confirmCheck,
  getClaim,
  money,
  openInvoicePdf,
  payClaim,
  reissueClaimInvoice,
  rejectClaim,
  removeCheck,
  shortDay,
  submitClaim,
  useRefreshBilling,
  withdrawClaim,
} from "./billingApi";

/**
 * El cobro de un programa como hoja paso a paso, igual que el acta de
 * instalación: creado → checklist → radicar → respuesta del programa →
 * pagado. El paso actual queda abierto; los demás se abren a mano.
 */
export function ClaimDetailPage() {
  const { claimId } = useParams<{ claimId: string }>();
  const { data: claim, isLoading } = useQuery({ queryKey: billingKeys.claim(claimId!), queryFn: () => getClaim(claimId!) });
  const { hasPermission } = useAuth();
  const [error, setError] = useState<string | null>(null);

  if (isLoading || !claim) return <p>Cargando…</p>;
  const puede = hasPermission("billing.submit");
  const pagar = hasPermission("invoices.record_payment");
  const abierto = claim.status === "preparing" || claim.status === "rejected";
  const retirado = claim.status === "withdrawn";
  const cumplidos = claim.requirements.filter((r) => r.met).length;
  const ultimo = claim.attempts[claim.attempts.length - 1];
  const radicado = claim.status === "submitted" || claim.status === "paid";

  const st = (done: boolean, current: boolean, locked = false): StepState =>
    done ? "done" : retirado ? "locked" : current ? "current" : locked ? "locked" : "pending";

  const steps: RecordStep[] = [
    {
      key: "created", title: "Cobro creado", state: "done",
      summary: `Tarifa del ${shortDay(claim.installation_date)} congelada · factura ${claim.invoice?.invoice_number ?? "anulada"}`,
      body: <InvoiceStep claim={claim} canReissue={!retirado && claim.status !== "paid" && puede} onError={setError} />,
    },
    {
      key: "checklist", title: "Checklist de radicación",
      state: st(radicado || (abierto && claim.ready_to_submit), abierto && !claim.ready_to_submit),
      summary: `${cumplidos} de ${claim.requirements.length} cumplidos`,
      body: <Checklist claim={claim} editable={abierto && puede} onError={setError} />,
    },
    {
      key: "submit", title: claim.status === "rejected" ? "Volver a radicar" : "Radicar ante el programa",
      state: st(radicado, abierto && claim.ready_to_submit, !claim.ready_to_submit),
      summary: radicado && ultimo
        ? `Radicado el ${shortDay(ultimo.submitted_on)}${ultimo.portal_reference ? ` · ref. ${ultimo.portal_reference}` : ""}`
        : claim.status === "rejected" ? "Corrige lo que pidió el programa y radica otra vez"
        : claim.ready_to_submit ? "Listo para radicar" : "Se habilita con el checklist completo",
      body: abierto && puede
        ? <SubmitStep claim={claim} onError={setError} />
        : <p className="acta-empty">{radicado ? "Radicado. La respuesta del programa se registra en el paso siguiente." : "Lo radica Administración o Contabilidad."}</p>,
    },
    {
      key: "response", title: "Respuesta del programa",
      state: st(claim.status === "paid", claim.status === "submitted", !radicado && claim.status !== "rejected"),
      chip: claim.status === "rejected" ? "Rechazado" : undefined,
      summary: claim.status === "rejected" && ultimo
        ? `Rechazado el ${shortDay(ultimo.resolved_on)}: ${ultimo.rejection_reason}`
        : claim.status === "submitted" ? "Esperando el pago o el rechazo"
        : claim.status === "paid" ? `Pagó el ${shortDay(claim.paid_on)}` : "Después de radicar",
      body: <ResponseStep claim={claim} canReject={puede} canPay={pagar} onError={setError} />,
    },
    {
      key: "paid", title: "Pagado", state: st(claim.status === "paid", false, claim.status !== "paid"),
      summary: claim.status === "paid"
        ? `${money(claim.paid_amount)}${claim.difference && Math.abs(claim.difference) >= 0.01 ? ` · diferencia ${money(claim.difference)}` : ""}`
        : "El expediente pasa a «Pagado» cuando todos sus cobros lo están",
      body: <PaidStep claim={claim} />,
    },
  ];

  return (
    <div className="acta-page">
      <Link to="/invoices" className="acta-back"><span aria-hidden="true">‹</span> Volver a cobros</Link>
      <article className="acta" aria-label={`Cobro ${claim.program_name}`}>
        <header className="acta-header">
          <div className="acta-title-row">
            <h1 className="acta-title">Cobro {claim.program_name}</h1>
            <span className="acta-amount money">{money(claim.amount)}</span>
          </div>
          <dl className="acta-meta">
            <div><dt>Cliente</dt><dd>{claim.customer_name ?? "—"}</dd></div>
            <div><dt>Expediente</dt><dd className="acta-data">
              <Link to={`/projects/${claim.project_id}`}>{claim.case_number ?? "Ver acta"}</Link></dd></div>
            <div><dt>Dirección</dt><dd>{claim.address ?? "—"}</dd></div>
            <div><dt>Estado</dt><dd><span className={`billing-chip is-${claim.status}`}>{CLAIM_STATUS_LABELS[claim.status]}</span></dd></div>
          </dl>
          {!claim.applies && <p className="acta-note">Fuera de la zona del programa: {claim.override_reason}</p>}
        </header>
        {error && <p className="form-error" role="alert">{error}</p>}
        {retirado && <p className="info-banner">Cobro retirado: {claim.withdrawn_reason}. El programa quedó libre para un cobro nuevo.</p>}
        <ActaSteps steps={steps} />
        {!retirado && claim.status !== "paid" && puede && <Withdraw claim={claim} onError={setError} />}
      </article>
    </div>
  );
}

type StepProps = { claim: ClaimDetail; onError: (m: string | null) => void };

function useClaimAction<T>(claim: ClaimDetail, fn: (v: T) => Promise<unknown>, onError: StepProps["onError"], after?: () => void) {
  const refresh = useRefreshBilling();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => { onError(null); after?.(); return refresh(claim.project_id); },
    onError: (err) => onError(apiErrorMessage(err)),
  });
}

function InvoiceStep({ claim, canReissue, onError }: StepProps & { canReissue: boolean }) {
  const [motivo, setMotivo] = useState("");
  const [abierto, setAbierto] = useState(false);
  const reissue = useClaimAction(claim, () => reissueClaimInvoice(claim.id, motivo), onError, () => { setAbierto(false); setMotivo(""); });
  const f = claim.invoice;
  if (!f) return <p className="acta-empty">Sin factura vigente.</p>;
  return (
    <div className="acta-body">
      <div className="billing-invoice-line">
        <div>
          <strong>{f.invoice_number}</strong>
          <span>Emitida el {shortDay(f.issue_date)} · vence el {shortDay(f.due_date)}</span>
          <span>El programa paga {money(f.amount)}; el cliente {money(f.customer_total)}.</span>
        </div>
        <div className="acta-actions">
          <button type="button" className="acta-btn" onClick={() => openInvoicePdf(f.id)}>Ver PDF</button>
          {canReissue && !abierto && <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(true)}>Refacturar</button>}
        </div>
      </div>
      {abierto && (
        <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); reissue.mutate(undefined); }}>
          <label htmlFor="refacturar">Motivo (la factura actual se anula y se emite otra)</label>
          <input id="refacturar" required minLength={3} value={motivo} onChange={(e) => setMotivo(e.target.value)}
            placeholder="Número de espacio equivocado" autoFocus />
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={reissue.isPending}>Anular y emitir otra</button>
            <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(false)}>Cancelar</button>
          </div>
        </form>
      )}
    </div>
  );
}

function Checklist({ claim, editable, onError }: StepProps & { editable: boolean }) {
  const confirmar = useClaimAction(claim, (code: string) => confirmCheck(claim.id, code), onError);
  const quitar = useClaimAction(claim, (code: string) => removeCheck(claim.id, code), onError);
  const cumplidos = claim.requirements.filter((r) => r.met).length;
  return (
    <div className="acta-requirements">
      <div className="acta-progress">
        <span>{cumplidos} de {claim.requirements.length} requisitos cumplidos</span>
        <span className="acta-progress-bar" aria-hidden="true">
          <span style={{ width: `${claim.requirements.length ? (cumplidos / claim.requirements.length) * 100 : 0}%` }} />
        </span>
      </div>
      <ul className="billing-req">
        {claim.requirements.map((r) => (
          <li key={r.code} className={r.met ? "is-met" : undefined}>
            <span className="acta-tick" aria-hidden="true">{r.met ? "✓" : ""}</span>
            <span className="billing-req-label">
              {r.label}
              {!r.met && r.detail && <small>{r.detail}</small>}
              {r.kind === "auto" && <small className="is-auto">Lo comprueba el sistema</small>}
              {r.met && r.kind === "manual" && r.confirmed_at && <small className="is-auto">Confirmado el {shortDay(r.confirmed_at)}</small>}
            </span>
            {editable && r.kind === "manual" && (
              r.met
                ? <button type="button" className="acta-btn is-quiet" onClick={() => quitar.mutate(r.code)}>Deshacer</button>
                : <button type="button" className="acta-btn is-line" onClick={() => confirmar.mutate(r.code)}>Confirmar</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SubmitStep({ claim, onError }: StepProps) {
  const [ref, setRef] = useState("");
  const [fecha, setFecha] = useState(localISODate());
  const radicar = useClaimAction(claim, () => submitClaim(claim.id, { portal_reference: ref || undefined, submitted_on: fecha }), onError);
  if (!claim.ready_to_submit) return <p className="acta-empty">Completa el checklist para radicar.</p>;
  return (
    <form className="panel-form" onSubmit={(e) => { e.preventDefault(); radicar.mutate(undefined); }}>
      <div className="field"><label htmlFor="rad-ref">Referencia del portal del programa</label>
        <input id="rad-ref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="LADWP-88231" /></div>
      <div className="field"><label htmlFor="rad-fecha">Fecha de radicación</label>
        <input id="rad-fecha" type="date" max={localISODate()} value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
      <button type="submit" className="acta-btn is-primary" disabled={radicar.isPending}>
        {radicar.isPending ? "Radicando…" : "Radicar"}
      </button>
    </form>
  );
}

function ResponseStep({ claim, canReject, canPay, onError }: StepProps & { canReject: boolean; canPay: boolean }) {
  const [monto, setMonto] = useState(String(claim.amount));
  const [fecha, setFecha] = useState(localISODate());
  const [ref, setRef] = useState("");
  const [rechazando, setRechazando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [categoria, setCategoria] = useState("documentary");
  const [devolver, setDevolver] = useState(false);
  const pagar = useClaimAction(claim, () => payClaim(claim.id, { amount: Number(monto), paid_on: fecha, reference: ref || undefined }), onError);
  const rechazar = useClaimAction(claim, () => rejectClaim(claim.id, {
    reason: motivo, category: categoria, return_to_technician: categoria === "technical" && devolver,
  }), onError, () => setRechazando(false));
  const diferencia = Number(monto) - claim.amount;

  return (
    <div className="acta-body">
      {claim.status === "submitted" && canPay && !rechazando && (
        <>
          <h4 className="acta-section-title">¿Llegó el pago?</h4>
          <form className="panel-form" onSubmit={(e) => { e.preventDefault(); pagar.mutate(undefined); }}>
            <div className="field"><label htmlFor="pago-monto">Monto recibido</label>
              <input id="pago-monto" type="number" step="0.01" min="0.01" required value={monto} onChange={(e) => setMonto(e.target.value)} /></div>
            <div className="field"><label htmlFor="pago-fecha">Fecha</label>
              <input id="pago-fecha" type="date" max={localISODate()} required value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
            <div className="field"><label htmlFor="pago-ref">Cheque o transferencia</label>
              <input id="pago-ref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="CHK-10442" /></div>
            <button type="submit" className="acta-btn is-primary" disabled={pagar.isPending}>Registrar pago</button>
          </form>
          {Math.abs(diferencia) >= 0.01 && (
            <p className={`billing-diff ${diferencia < 0 ? "is-short" : "is-over"}`}>
              {diferencia < 0 ? `Llega ${money(-diferencia)} menos que la tarifa` : `Llega ${money(diferencia)} más que la tarifa`}: la diferencia queda registrada.
            </p>
          )}
        </>
      )}
      {claim.status === "submitted" && canReject && (
        rechazando ? (
          <form className="panel-form" onSubmit={(e) => { e.preventDefault(); rechazar.mutate(undefined); }}>
            <div className="field"><label htmlFor="rech-cat">Tipo de rechazo</label>
              <select id="rech-cat" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
                {Object.entries(REJECTION_CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div className="field billing-span"><label htmlFor="rech-motivo">Qué dijo el programa</label>
              <input id="rech-motivo" required minLength={3} value={motivo} onChange={(e) => setMotivo(e.target.value)}
                placeholder="Falta la firma del cliente en el formulario" /></div>
            {categoria === "technical" && (
              <label className="billing-check billing-span">
                <input type="checkbox" checked={devolver} onChange={(e) => setDevolver(e.target.checked)} />
                Devolver el acta al técnico para que corrija (el expediente sigue en cobro)
              </label>
            )}
            <div className="acta-actions billing-span" style={{ justifyContent: "flex-start" }}>
              <button type="submit" className="acta-btn is-primary" disabled={rechazar.isPending}>Registrar rechazo</button>
              <button type="button" className="acta-btn is-quiet" onClick={() => setRechazando(false)}>Cancelar</button>
            </div>
          </form>
        ) : (
          <div className="acta-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
            <button type="button" className="acta-btn is-quiet" onClick={() => setRechazando(true)}>El programa lo rechazó…</button>
          </div>
        )
      )}
      {claim.attempts.length > 0 && (
        <>
          <h4 className="acta-section-title">Radicaciones</h4>
          <ol className="acta-history">
            {claim.attempts.map((a, n) => (
              <li key={a.id} className={a.result === "rejected" ? "is-returned" : a.result === "paid" ? "is-confirmed" : undefined}>
                <strong>Intento {n + 1}</strong>
                <span>radicado el {shortDay(a.submitted_on)}{a.portal_reference ? ` · ref. ${a.portal_reference}` : ""}</span>
                <p>{a.result === "pending" ? "Esperando respuesta."
                  : a.result === "paid" ? `Pagado el ${shortDay(a.resolved_on)}.`
                  : `Rechazado el ${shortDay(a.resolved_on)} (${REJECTION_CATEGORIES[a.rejection_category ?? ""]?.toLowerCase()}): ${a.rejection_reason}`}</p>
              </li>
            ))}
          </ol>
        </>
      )}
      {claim.attempts.length === 0 && <p className="acta-empty">Todavía no se ha radicado.</p>}
    </div>
  );
}

function PaidStep({ claim }: { claim: ClaimDetail }) {
  if (claim.status !== "paid") return <p className="acta-empty">Pendiente del pago del programa.</p>;
  const d = claim.difference ?? 0;
  return (
    <dl className="billing-paid">
      <div><dt>Recibido</dt><dd className="money">{money(claim.paid_amount)}</dd></div>
      <div><dt>Fecha</dt><dd>{shortDay(claim.paid_on)}</dd></div>
      <div><dt>Referencia</dt><dd>{claim.payment_reference ?? "—"}</dd></div>
      <div><dt>Diferencia con la tarifa</dt>
        <dd className={`money ${Math.abs(d) >= 0.01 ? (d < 0 ? "billing-diff is-short" : "billing-diff is-over") : ""}`}>{money(d)}</dd></div>
    </dl>
  );
}

function Withdraw({ claim, onError }: StepProps) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  const retirar = useClaimAction(claim, () => withdrawClaim(claim.id, motivo), onError, () => setAbierto(false));
  return (
    <footer className="acta-footer">
      {!abierto ? (
        <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(true)}>Retirar este cobro…</button>
      ) : (
        <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); retirar.mutate(undefined); }}>
          <label htmlFor="retirar">Por qué se retira (anula la factura y libera el programa)</label>
          <input id="retirar" required minLength={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={retirar.isPending}>Retirar cobro</button>
            <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(false)}>Cancelar</button>
          </div>
        </form>
      )}
    </footer>
  );
}
