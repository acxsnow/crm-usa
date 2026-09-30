import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "./billing.css";
import { useAuth } from "@/features/auth/AuthContext";
import { listCustomers } from "@/features/crm/api";
import { ActaSteps, type RecordStep, type StepState } from "@/features/field-ops/components/InstallationRecord";
import { apiErrorMessage, localISODate } from "@/features/field-ops/module5Api";
import { LINE_KIND_LABELS, type Invoice, type LineInput, type QuoteDetail } from "@/types/billing";
import { recordInvoicePayment } from "./api";
import {
  acceptQuote,
  billingKeys,
  getQuote,
  issueInvoice,
  money,
  openInvoicePdf,
  rejectQuote,
  replaceInvoiceLines,
  reviseQuote,
  sendQuote,
  shortDay,
  updateQuote,
} from "./billingApi";
import { LinesEditor, toInputs } from "./LinesEditor";

const VERSION_STATUS: Record<QuoteDetail["status"], string> = {
  draft: "borrador", sent: "enviada", accepted: "aceptada", rejected: "no aceptada",
  superseded: "reemplazada", expired: "vencida",
};

/**
 * Trabajo particular como hoja paso a paso (spec D6.7): armar la cotización →
 * respuesta del cliente → factura → pagos. Un borrador se edita; una enviada
 * se ajusta con una versión nueva y la anterior queda en el historial.
 */
export function QuoteDetailPage() {
  const { quoteId } = useParams<{ quoteId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const { data: q } = useQuery({ queryKey: billingKeys.quote(quoteId!), queryFn: () => getQuote(quoteId!) });
  const { data: customers } = useQuery({ queryKey: ["customers-all"], queryFn: listCustomers });
  const [error, setError] = useState<string | null>(null);
  const [lineas, setLineas] = useState<LineInput[]>([]);
  const [motivo, setMotivo] = useState("");
  const [rechazando, setRechazando] = useState(false);
  useEffect(() => { if (q) setLineas(toInputs(q.lines)); }, [q]);

  const refresh = () => Promise.all([
    qc.invalidateQueries({ queryKey: ["quote"] }), qc.invalidateQueries({ queryKey: billingKeys.quotes }),
    qc.invalidateQueries({ queryKey: ["invoices"] }), qc.invalidateQueries({ queryKey: billingKeys.dashboard }),
  ]);
  const act = <T,>(fn: () => Promise<T>, after?: (r: T) => void) => ({
    mutationFn: fn,
    onSuccess: (r: T) => { setError(null); after?.(r); return refresh(); },
    onError: (err: unknown) => setError(apiErrorMessage(err)),
  });
  const guardar = useMutation(act(() => updateQuote(quoteId!, { lines: lineas })));
  const enviar = useMutation(act(async () => { await updateQuote(quoteId!, { lines: lineas }); return sendQuote(quoteId!); }));
  const ajustar = useMutation(act(() => reviseQuote(quoteId!), (n) => navigate(`/invoices/quotes/${n.id}`)));
  const aceptar = useMutation(act(() => acceptQuote(quoteId!)));
  const rechazar = useMutation(act(() => rejectQuote(quoteId!, motivo), () => setRechazando(false)));

  if (!q) return <p>Cargando…</p>;
  const puede = hasPermission("quotes.manage");
  const borrador = q.status === "draft";
  const reemplazada = q.status === "superseded";
  const aceptada = q.status === "accepted";
  const f = q.invoice;
  const emitida = f?.document_status === "issued";
  const pagada = emitida && f!.balance <= 0;
  const cliente = customers?.find((c) => c.id === q.customer_id)?.legal_name ?? "Cliente";
  const st = (done: boolean, current: boolean, locked = false): StepState =>
    done ? "done" : reemplazada ? "locked" : current ? "current" : locked ? "locked" : "pending";

  const steps: RecordStep[] = [
    {
      key: "quote", title: "Armar la cotización", state: st(!borrador, borrador),
      summary: `${q.lines.length} ${q.lines.length === 1 ? "línea" : "líneas"} · ${money(q.total)}${q.sent_at ? ` · enviada el ${shortDay(q.sent_at)}` : ""}`,
      body: borrador && puede ? (
        <form onSubmit={(e) => { e.preventDefault(); enviar.mutate(); }}>
          <LinesEditor lines={lineas} onChange={setLineas} />
          <div className="acta-actions" style={{ marginTop: "0.9rem" }}>
            <button type="button" className="acta-btn" disabled={guardar.isPending} onClick={() => guardar.mutate()}>Guardar borrador</button>
            <button type="submit" className="acta-btn is-primary" disabled={enviar.isPending}>Guardar y marcar como enviada</button>
          </div>
        </form>
      ) : <LinesTable lines={q.lines} />,
    },
    {
      key: "answer", title: "Respuesta del cliente",
      state: st(aceptada, ["sent", "expired", "rejected"].includes(q.status), borrador),
      chip: q.status === "rejected" ? "No aceptada" : q.status === "expired" ? "Vencida" : undefined,
      summary: aceptada ? `Aceptada el ${shortDay(q.decided_at)}`
        : q.status === "rejected" ? `No la aceptó: ${q.rejection_reason}`
        : q.status === "expired" ? `Venció el ${shortDay(q.valid_until)}; ajústala con vigencia nueva`
        : q.status === "sent" ? `Esperando respuesta${q.valid_until ? ` · vigente hasta el ${shortDay(q.valid_until)}` : ""}`
        : reemplazada ? "Esta versión se reemplazó por otra" : "Después de enviarla",
      body: puede && ["sent", "rejected", "expired"].includes(q.status) ? (
        <div className="acta-body">
          {!rechazando ? (
            <div className="acta-actions" style={{ justifyContent: "flex-start" }}>
              {q.status === "sent" && <button type="button" className="acta-btn is-primary" onClick={() => aceptar.mutate()}>El cliente aceptó</button>}
              <button type="button" className="acta-btn" onClick={() => ajustar.mutate()}>Ajustar precio o líneas (versión {q.version + 1})</button>
              {q.status === "sent" && <button type="button" className="acta-btn is-quiet" onClick={() => setRechazando(true)}>No la aceptó…</button>}
            </div>
          ) : (
            <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); rechazar.mutate(); }}>
              <label htmlFor="cot-rechazo">Por qué no la aceptó</label>
              <input id="cot-rechazo" required minLength={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />
              <div className="acta-actions">
                <button type="submit" className="acta-btn is-primary">Registrar</button>
                <button type="button" className="acta-btn is-quiet" onClick={() => setRechazando(false)}>Cancelar</button>
              </div>
            </form>
          )}
        </div>
      ) : <p className="acta-empty">{aceptada ? "Aceptada: la factura se armó con las mismas líneas." : "Se registra cuando el cliente responda."}</p>,
    },
    {
      key: "invoice", title: "Factura", state: st(Boolean(emitida), aceptada && !emitida, !aceptada),
      summary: emitida ? `${f!.invoice_number} · emitida el ${shortDay(f!.issue_date)} · ${f!.due_date ? `vence el ${shortDay(f!.due_date)}` : "sin fecha de vencimiento"}`
        : aceptada ? "En borrador: ajústala si hace falta y emítela" : "Se arma al aceptar la cotización",
      body: f ? <InvoiceStep invoice={f} onChanged={refresh} onError={setError} /> : <p className="acta-empty">Sin factura todavía.</p>,
    },
    {
      key: "payments", title: "Pagos del cliente", state: st(Boolean(pagada), Boolean(emitida && !pagada), !emitida),
      chip: pagada ? "Pagada" : undefined,
      summary: emitida ? `Pagado ${money(f!.paid_amount)} de ${money(f!.amount)} · saldo ${money(f!.balance)}` : "Después de emitir la factura",
      body: f && emitida ? <PaymentsStep invoice={f} onChanged={refresh} onError={setError} /> : <p className="acta-empty">Después de emitir la factura.</p>,
    },
  ];

  return (
    <div className="acta-page">
      <Link to="/invoices?tab=quotes" className="acta-back"><span aria-hidden="true">‹</span> Volver a cotizaciones</Link>
      <article className="acta" aria-label={`Cotización ${q.quote_number}`}>
        <header className="acta-header">
          <div className="acta-title-row">
            <h1 className="acta-title">{q.title ?? "Trabajo particular"}</h1>
            <span className="acta-amount money">{money(q.total)}</span>
          </div>
          <dl className="acta-meta">
            <div><dt>Cliente</dt><dd>{cliente}</dd></div>
            <div><dt>Cotización</dt><dd className="acta-data">{q.quote_number} · v{q.version}</dd></div>
            <div><dt>Vigente hasta</dt><dd>{shortDay(q.valid_until)}</dd></div>
            <div><dt>Instalación</dt><dd>{q.project_id ? <Link to={`/projects/${q.project_id}`}>Ver acta</Link> : "Sin instalación"}</dd></div>
          </dl>
        </header>
        {error && <p className="form-error" role="alert">{error}</p>}
        {reemplazada && (
          <p className="info-banner">Esta es una versión anterior y ya no se modifica. Mira la versión vigente abajo.</p>
        )}
        <ActaSteps steps={steps} />
        {q.versions.length > 1 && (
          <footer className="acta-footer">
            <h4 className="acta-section-title">Versiones</h4>
            <ol className="acta-history">
              {q.versions.map((v) => (
                <li key={v.id} className={v.status === "accepted" ? "is-confirmed" : undefined}>
                  {v.id === q.id ? <strong>Versión {v.version} (esta)</strong> : <Link to={`/invoices/quotes/${v.id}`}>Versión {v.version}</Link>}
                  <span>{money(v.total)} · {shortDay(v.created_at)} · {VERSION_STATUS[v.status]}</span>
                </li>
              ))}
            </ol>
          </footer>
        )}
      </article>
    </div>
  );
}

function LinesTable({ lines }: { lines: QuoteDetail["lines"] }) {
  return (
    <div className="billing-table-wrap">
      <table className="billing-table">
        <thead><tr><th>Tipo</th><th>Descripción</th><th className="num">Cant.</th><th className="num">Precio</th><th className="num">Importe</th></tr></thead>
        <tbody>
          {lines.map((l) => (
            <tr key={l.id}><td>{LINE_KIND_LABELS[l.kind] ?? l.kind}</td><td>{l.description}</td>
              <td className="num">{l.quantity}</td><td className="num">{money(l.unit_price)}</td><td className="num">{money(l.amount)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type InvoiceProps = { invoice: Invoice; onChanged: () => Promise<unknown>; onError: (m: string | null) => void };

/** La factura que salió de la cotización: borrador ajustable y emitir. */
function InvoiceStep({ invoice, onChanged, onError }: InvoiceProps) {
  const { hasPermission } = useAuth();
  const [lineas, setLineas] = useState<LineInput[]>(toInputs(invoice.lines));
  const [vence, setVence] = useState("");
  useEffect(() => setLineas(toInputs(invoice.lines)), [invoice]);
  const handlers = { onSuccess: () => { onError(null); return onChanged(); }, onError: (e: unknown) => onError(apiErrorMessage(e)) };
  const guardar = useMutation({ mutationFn: () => replaceInvoiceLines(invoice.id, lineas), ...handlers });
  const emitir = useMutation({
    mutationFn: async () => { await replaceInvoiceLines(invoice.id, lineas); return issueInvoice(invoice.id, vence || undefined); },
    ...handlers,
  });

  if (invoice.document_status !== "draft") {
    return (
      <div className="billing-invoice-line">
        <div><strong>{invoice.invoice_number}</strong><span>Total {money(invoice.amount)} · ya no se edita (se anula y se emite otra)</span></div>
        <button type="button" className="acta-btn" onClick={() => openInvoicePdf(invoice.id)}>Ver PDF</button>
      </div>
    );
  }
  if (!hasPermission("invoices.update")) return <p className="acta-empty">Contabilidad la revisa y la emite.</p>;
  return (
    <form onSubmit={(e) => { e.preventDefault(); emitir.mutate(); }}>
      <LinesEditor lines={lineas} onChange={setLineas} />
      <div className="panel-form" style={{ marginTop: "0.9rem" }}>
        <div className="field"><label htmlFor="fac-vence">Vence</label>
          <input id="fac-vence" type="date" min={localISODate()} value={vence} onChange={(e) => setVence(e.target.value)} /></div>
        <button type="button" className="acta-btn" disabled={guardar.isPending} onClick={() => guardar.mutate()}>Guardar borrador</button>
        <button type="submit" className="acta-btn is-primary" disabled={!hasPermission("invoices.create") || emitir.isPending}>
          {emitir.isPending ? "Emitiendo…" : "Emitir factura"}
        </button>
      </div>
    </form>
  );
}

function PaymentsStep({ invoice, onChanged, onError }: InvoiceProps) {
  const { hasPermission } = useAuth();
  const [monto, setMonto] = useState("");
  const [fecha, setFecha] = useState(localISODate());
  const [ref, setRef] = useState("");
  const pagar = useMutation({
    mutationFn: () => recordInvoicePayment(invoice.id, { amount: Number(monto), paid_at: fecha, reference: ref || undefined }),
    onSuccess: () => { setMonto(""); setRef(""); onError(null); return onChanged(); },
    onError: (e: unknown) => onError(apiErrorMessage(e)),
  });
  return (
    <div className="acta-body">
      <dl className="billing-paid">
        <div><dt>Total</dt><dd className="money">{money(invoice.amount)}</dd></div>
        <div><dt>Pagado</dt><dd className="money">{money(invoice.paid_amount)}</dd></div>
        <div><dt>Saldo</dt><dd className={`money${invoice.status === "overdue" ? " billing-diff is-short" : ""}`}>{money(invoice.balance)}</dd></div>
        <div><dt>Vence</dt><dd>{invoice.due_date ? shortDay(invoice.due_date) : "Sin fecha"}{invoice.status === "overdue" ? " · vencida" : ""}</dd></div>
      </dl>
      {invoice.payments.length > 0 && (
        <ol className="acta-history">
          {invoice.payments.map((p) => (
            <li key={p.id} className="is-confirmed"><strong>{money(p.amount)}</strong><span>{shortDay(p.paid_at)}{p.reference ? ` · ${p.reference}` : ""}</span></li>
          ))}
        </ol>
      )}
      {invoice.balance > 0 && hasPermission("invoices.record_payment") && (
        <form className="panel-form" style={{ marginTop: "0.9rem" }} onSubmit={(e) => { e.preventDefault(); pagar.mutate(); }}>
          <div className="field"><label htmlFor="pp-monto">Pago recibido</label>
            <input id="pp-monto" type="number" step="0.01" min="0.01" required value={monto}
              onChange={(e) => setMonto(e.target.value)} placeholder={String(invoice.balance)} /></div>
          <div className="field"><label htmlFor="pp-fecha">Fecha</label>
            <input id="pp-fecha" type="date" required value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
          <div className="field"><label htmlFor="pp-ref">Referencia</label>
            <input id="pp-ref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="Zelle, cheque…" /></div>
          <button type="submit" className="acta-btn is-primary" disabled={pagar.isPending}>Registrar pago</button>
        </form>
      )}
    </div>
  );
}
