import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PaginationControls } from "@/components/PaginationControls";
import { useAuth } from "@/features/auth/AuthContext";
import { listCustomers } from "@/features/crm/api";
import { apiErrorMessage, localISODate } from "@/features/field-ops/module5Api";
import { useSearchTextFromUrl } from "@/lib/useSearchTextFromUrl";
import { INVOICE_STATUS_LABELS, type Invoice } from "@/types/billing";
import {
  downloadInvoicesCsv,
  fetchInvoiceAttachmentObjectUrl,
  getFinanceDashboard,
  listInvoicesPage,
  markInvoiceSent,
  recordInvoicePayment,
  uploadInvoiceAttachment,
} from "./api";
import { money, openInvoicePdf, shortDay } from "./billingApi";
import { CollectPayment } from "@/features/payments/CollectPayment";

const PAGE_SIZE = 20;

const TIPOS = [
  { key: "", label: "Todas" },
  { key: "rebate", label: "A programas" },
  { key: "particular", label: "A clientes" },
];
const ESTADOS = [
  { key: "", label: "Cualquier estado" },
  { key: "unpaid", label: "Sin pagar" },
  { key: "partial", label: "Pago parcial" },
  { key: "overdue", label: "Vencidas" },
  { key: "paid", label: "Pagadas" },
  { key: "draft", label: "Borradores" },
  { key: "void", label: "Anuladas" },
];

/**
 * Todas las facturas, las de programas y las de clientes. Una sola hoja: los
 * totales arriba y una fila por factura; tocarla abre su detalle (PDF, pagos,
 * comprobantes). Las de rebate se cobran desde su cobro; las particulares,
 * desde su cotización o aquí mismo.
 */
export function InvoicesTab() {
  const [tipo, setTipo] = useState("");
  const [estado, setEstado] = useState("");
  const [page, setPage] = useState(1);
  const [abierta, setAbierta] = useState<string | null>(null);
  // Número de factura o cliente; también llega del buscador global (?q=FAC-…).
  const [buscar, setBuscar] = useState("");
  const [q, setQ] = useState("");
  const [abrirSiEsUna, setAbrirSiEsUna] = useState(false);
  useSearchTextFromUrl((texto) => { setBuscar(texto); setQ(texto); setPage(1); setAbrirSiEsUna(true); });
  useEffect(() => {
    const t = setTimeout(() => { setQ((antes) => (antes === buscar.trim() ? antes : buscar.trim())); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [buscar]);
  const params: Record<string, string> = {};
  if (tipo) params.kind = tipo;
  if (estado) params.status = estado;
  if (q) params.q = q;
  const { data, isLoading } = useQuery({
    queryKey: ["invoices", page, params],
    queryFn: () => listInvoicesPage(page, PAGE_SIZE, params),
  });
  // Si el buscador global trajo una sola factura, se abre su detalle de una vez.
  useEffect(() => {
    if (!abrirSiEsUna || !data || params.q !== q) return;
    if (data.items.length === 1) setAbierta(data.items[0].id);
    setAbrirSiEsUna(false);
  }, [abrirSiEsUna, data, q, params.q]);
  // El tablero financiero exige `dashboards.finance` (Contabilidad, Gerencia):
  // Administración ve la lista sin los totales en vez de recibir un 403 (QA-03).
  const { hasPermission } = useAuth();
  const { data: resumen } = useQuery({
    queryKey: ["finance-dashboard"], queryFn: getFinanceDashboard, enabled: hasPermission("dashboards.finance"),
  });
  const { data: customers } = useQuery({ queryKey: ["customers-all"], queryFn: listCustomers });
  const cliente = (id: string) => customers?.find((c) => c.id === id)?.legal_name ?? "Cliente";
  const filtrar = (fn: () => void) => { fn(); setPage(1); setAbierta(null); };

  return (
    <section className="acta billing-list" aria-label="Facturas">
      <header className="acta-header">
        <div className="acta-title-row">
          <h2 className="acta-title">Facturas</h2>
          <button type="button" className="acta-btn is-line" onClick={() => downloadInvoicesCsv()}>Exportar CSV</button>
        </div>
        {resumen && (
          <dl className="billing-totals">
            <div><dt>Facturado</dt><dd className="money">{money(resumen.total_invoiced)}</dd><small>{resumen.invoice_count} facturas emitidas</small></div>
            <div><dt>Pagado</dt><dd className="money is-ok">{money(resumen.total_paid)}</dd></div>
            <div><dt>Saldo por cobrar</dt><dd className="money">{money(resumen.total_outstanding)}</dd><small>{resumen.due_soon_count} vencen en 7 días</small></div>
            <div><dt>Vencido</dt><dd className={`money${resumen.overdue_count ? " is-late" : ""}`}>{money(resumen.total_overdue)}</dd>
              <small>{resumen.overdue_count} {resumen.overdue_count === 1 ? "factura" : "facturas"}</small></div>
          </dl>
        )}
      </header>

      <div className="billing-filters">
        <div className="billing-pills" role="group" aria-label="A quién se factura">
          {TIPOS.map((t) => (
            <button key={t.key} type="button" aria-pressed={tipo === t.key} className={`billing-pill${tipo === t.key ? " is-on" : ""}`}
              onClick={() => filtrar(() => setTipo(t.key))}>{t.label}</button>
          ))}
        </div>
        <select aria-label="Estado de la factura" value={estado} onChange={(e) => filtrar(() => setEstado(e.target.value))}>
          {ESTADOS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <input type="search" aria-label="Buscar factura" placeholder="Número o cliente" value={buscar}
          onChange={(e) => setBuscar(e.target.value)} />
      </div>

      {isLoading ? <p className="acta-empty">Cargando…</p> : (data?.items ?? []).length === 0 ? (
        <p className="acta-empty">No hay facturas con estos filtros.</p>
      ) : (
        <ul className="invoice-rows">
          {(data?.items ?? []).map((inv) => (
            <li key={inv.id} className={abierta === inv.id ? "is-open" : undefined}>
              <button type="button" className="invoice-row" aria-expanded={abierta === inv.id}
                onClick={() => setAbierta(abierta === inv.id ? null : inv.id)}>
                <span className="invoice-row-main">
                  <strong>{cliente(inv.customer_id)}</strong>
                  <span><span className="money">{inv.invoice_number}</span> · {inv.kind === "rebate" ? inv.funder_program ?? "Programa" : "Trabajo particular"}</span>
                </span>
                <span className="invoice-row-fig"><small>Monto</small><span className="money">{money(inv.amount)}</span></span>
                <span className="invoice-row-fig"><small>Saldo</small><span className="money">{money(inv.document_status === "issued" ? inv.balance : 0)}</span></span>
                <span className={`billing-chip is-${inv.status}`}>{INVOICE_STATUS_LABELS[inv.status]}</span>
                <span className="invoice-row-fig is-date"><small>Vence</small><span>{inv.due_date ? shortDay(inv.due_date) : "—"}</span></span>
                <span className="invoice-row-caret" aria-hidden="true">›</span>
              </button>
              {abierta === inv.id && <InvoiceDetail invoice={inv} />}
            </li>
          ))}
        </ul>
      )}
      {data && data.total > PAGE_SIZE && (
        <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
      )}
    </section>
  );
}

function InvoiceDetail({ invoice }: { invoice: Invoice }) {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [monto, setMonto] = useState("");
  const [fecha, setFecha] = useState(localISODate());
  const [ref, setRef] = useState("");
  const archivo = useRef<HTMLInputElement>(null);
  const refresh = () => Promise.all([
    qc.invalidateQueries({ queryKey: ["invoices"] }), qc.invalidateQueries({ queryKey: ["finance-dashboard"] }),
  ]);
  const handlers = { onSuccess: () => { setError(null); return refresh(); }, onError: (e: unknown) => setError(apiErrorMessage(e)) };
  const pagar = useMutation({
    mutationFn: () => recordInvoicePayment(invoice.id, { amount: Number(monto), paid_at: fecha, reference: ref || undefined }),
    ...handlers, onSuccess: () => { setMonto(""); setRef(""); setError(null); return refresh(); },
  });
  const enviada = useMutation({ mutationFn: () => markInvoiceSent(invoice.id), ...handlers });
  const subir = useMutation({
    mutationFn: (f: File) => uploadInvoiceAttachment(invoice.id, f),
    ...handlers, onSettled: () => { if (archivo.current) archivo.current.value = ""; },
  });
  const verAdjunto = async (id: string) => window.open(await fetchInvoiceAttachmentObjectUrl(id), "_blank", "noopener");
  const emitida = invoice.document_status === "issued";
  // Las de rebate se cobran desde su cobro: allí queda el intento, la
  // diferencia y el paso del expediente a «Pagado».
  const cobraAqui = emitida && invoice.kind === "particular" && invoice.balance > 0 && hasPermission("invoices.record_payment");

  return (
    <div className="invoice-detail">
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="invoice-detail-actions">
        {invoice.document_status !== "draft" && <button type="button" className="acta-btn" onClick={() => openInvoicePdf(invoice.id)}>Ver PDF</button>}
        {invoice.claim_id && <Link className="acta-btn" to={`/invoices/claims/${invoice.claim_id}`}>Ir al cobro</Link>}
        {invoice.quote_id && <Link className="acta-btn" to={`/invoices/quotes/${invoice.quote_id}`}>Ir a la cotización</Link>}
        {emitida && !invoice.sent_at && invoice.status !== "paid" && (
          <button type="button" className="acta-btn is-quiet" onClick={() => enviada.mutate()}>Marcar como enviada</button>
        )}
      </div>
      <dl className="billing-paid">
        <div><dt>Emitida</dt><dd>{invoice.issue_date ? shortDay(invoice.issue_date) : "Borrador"}</dd></div>
        <div><dt>Enviada</dt><dd>{invoice.sent_at ? shortDay(invoice.sent_at) : "No"}</dd></div>
        <div><dt>Pagado</dt><dd className="money">{money(invoice.paid_amount)}</dd></div>
        <div><dt>Saldo</dt><dd className="money">{money(emitida ? invoice.balance : 0)}</dd></div>
      </dl>
      {invoice.void_reason && <p className="acta-note">Anulada: {invoice.void_reason}</p>}
      {invoice.payments.length > 0 && (
        <ol className="acta-history">
          {invoice.payments.map((p) => (
            <li key={p.id} className="is-confirmed"><strong>{money(p.amount)}</strong><span>{shortDay(p.paid_at)}{p.method ? ` · ${p.method}` : ""}
              {p.provider ? "" : p.reference ? ` · ${p.reference}` : ""}{p.fee_amount ? ` · comisión ${money(p.fee_amount)}` : ""}</span></li>
          ))}
        </ol>
      )}
      {/* Cobro en línea (como Housecall Pro): enlace por correo o SMS, o QR en la obra. */}
      {emitida && invoice.kind === "particular" && invoice.balance > 0 && hasPermission("payments.collect") && (
        <CollectPayment invoiceId={invoice.id} balance={Number(invoice.balance)} onPaid={() => { void refresh(); }} />
      )}
      {cobraAqui && (
        <form className="panel-form" onSubmit={(e) => { e.preventDefault(); pagar.mutate(); }}>
          <div className="field"><label htmlFor={`pago-${invoice.id}`}>Pago recibido</label>
            <input id={`pago-${invoice.id}`} type="number" step="0.01" min="0.01" required value={monto}
              onChange={(e) => setMonto(e.target.value)} placeholder={String(invoice.balance)} /></div>
          <div className="field"><label htmlFor={`fecha-${invoice.id}`}>Fecha</label>
            <input id={`fecha-${invoice.id}`} type="date" required value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
          <div className="field"><label htmlFor={`ref-${invoice.id}`}>Referencia</label>
            <input id={`ref-${invoice.id}`} value={ref} onChange={(e) => setRef(e.target.value)} placeholder="Zelle, cheque…" /></div>
          <button type="submit" className="acta-btn is-primary" disabled={pagar.isPending}>Registrar pago</button>
        </form>
      )}
      <div className="invoice-attachments">
        <span>Comprobantes</span>
        {invoice.attachments.map((a) => (
          <button key={a.id} type="button" className="billing-file" onClick={() => verAdjunto(a.id)}>{a.original_filename ?? "archivo"}</button>
        ))}
        {hasPermission("invoices.update") && (
          <label className="acta-btn is-line">
            <input ref={archivo} type="file" accept="image/*,application/pdf" className="visually-hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) subir.mutate(f); }} />
            {subir.isPending ? "Subiendo…" : "Adjuntar comprobante"}
          </label>
        )}
        {invoice.attachments.length === 0 && !hasPermission("invoices.update") && <span className="acta-empty">Sin comprobantes.</span>}
      </div>
    </div>
  );
}
