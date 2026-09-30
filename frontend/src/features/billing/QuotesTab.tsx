import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { listCustomers } from "@/features/crm/api";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import type { LineInput, QuoteStatus } from "@/types/billing";
import { billingKeys, createQuote, listQuotes, money, shortDay } from "./billingApi";
import { LinesEditor, emptyLine } from "./LinesEditor";

const FILTROS: { key: string; label: string; match: (s: QuoteStatus) => boolean }[] = [
  { key: "all", label: "Todas", match: () => true },
  { key: "draft", label: "Borradores", match: (s) => s === "draft" },
  { key: "sent", label: "Esperando respuesta", match: (s) => s === "sent" },
  { key: "accepted", label: "Aceptadas", match: (s) => s === "accepted" },
  { key: "closed", label: "No aceptadas o vencidas", match: (s) => s === "rejected" || s === "expired" },
];

/** Trabajo particular: cotizaciones vigentes y crear una nueva. */
export function QuotesTab() {
  const { data: quotes, isLoading } = useQuery({ queryKey: billingKeys.quotes, queryFn: () => listQuotes() });
  const { data: customers } = useQuery({ queryKey: ["customers-all"], queryFn: listCustomers });
  const [nueva, setNueva] = useState(false);
  const [filtro, setFiltro] = useState("all");
  const nombre = (id: string) => customers?.find((c) => c.id === id)?.legal_name ?? "Cliente";
  const activo = FILTROS.find((f) => f.key === filtro)!;
  const visibles = (quotes ?? []).filter((q) => activo.match(q.status));

  return (
    <>
      {nueva && (
        <section className="acta billing-list" aria-label="Nueva cotización">
          <header className="billing-list-head"><h2>Nueva cotización</h2>
            <p>Trabajo que paga el cliente. Queda en borrador hasta que la marques como enviada.</p></header>
          <NewQuote customers={customers ?? []} onCancel={() => setNueva(false)} />
        </section>
      )}

      <section className="acta billing-list" aria-label="Cotizaciones">
        <header className="acta-header">
          <div className="acta-title-row">
            <h2 className="acta-title">Cotizaciones</h2>
            {!nueva && <button type="button" className="acta-btn is-primary" onClick={() => setNueva(true)}>Nueva cotización</button>}
          </div>
          <dl className="billing-totals">
            {[
              { label: "Esperando respuesta", st: ["sent"] },
              { label: "Aceptadas", st: ["accepted"] },
              { label: "En borrador", st: ["draft"] },
              { label: "No aceptadas o vencidas", st: ["rejected", "expired"] },
            ].map(({ label, st }) => {
              const grupo = (quotes ?? []).filter((q) => st.includes(q.status));
              return (
                <div key={label}><dt>{label}</dt>
                  <dd className={`money${st[0] === "accepted" && grupo.length ? " is-ok" : ""}`}>{money(grupo.reduce((a, q) => a + q.total, 0))}</dd>
                  <small>{grupo.length} {grupo.length === 1 ? "cotización" : "cotizaciones"}</small></div>
              );
            })}
          </dl>
        </header>
        <div className="billing-pills" role="group" aria-label="Filtrar por estado">
          {FILTROS.map((f) => {
            const n = (quotes ?? []).filter((q) => f.match(q.status)).length;
            return (
              <button key={f.key} type="button" aria-pressed={filtro === f.key}
                className={`billing-pill${filtro === f.key ? " is-on" : ""}`} onClick={() => setFiltro(f.key)}>
                {f.label} <span>{n}</span>
              </button>
            );
          })}
        </div>
        {isLoading ? <p className="acta-empty">Cargando…</p> : visibles.length === 0 ? (
          <p className="acta-empty">{(quotes ?? []).length ? "Ninguna cotización en este estado." : "Todavía no hay cotizaciones. Crea la primera con «Nueva cotización»."}</p>
        ) : (
          <ul className="invoice-rows">
            {visibles.map((q) => (
              <li key={q.id}>
                <Link to={`/invoices/quotes/${q.id}`} className="quote-row">
                  <span className="invoice-row-main">
                    <strong>{nombre(q.customer_id)}</strong>
                    <span>{q.title ?? "Trabajo particular"} · <span className="money">{q.quote_number}</span> v{q.version}</span>
                  </span>
                  <span className="invoice-row-fig"><small>Total</small><span className="money">{money(q.total)}</span></span>
                  <span className={`billing-chip is-${q.status}`}>{q.status_label}</span>
                  <span className="invoice-row-fig is-date"><small>Vigente hasta</small><span>{q.valid_until ? shortDay(q.valid_until) : "Sin fecha"}</span></span>
                  <span className="invoice-row-caret" aria-hidden="true">›</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

function NewQuote({ customers, onCancel }: { customers: { id: string; legal_name: string }[]; onCancel: () => void }) {
  const navigate = useNavigate();
  const [cliente, setCliente] = useState("");
  const [titulo, setTitulo] = useState("");
  const [vigencia, setVigencia] = useState("");
  const [lineas, setLineas] = useState<LineInput[]>([emptyLine()]);
  const [error, setError] = useState<string | null>(null);
  const crear = useMutation({
    mutationFn: () => createQuote({ customer_id: cliente, title: titulo || undefined, valid_until: vigencia || undefined, lines: lineas }),
    onSuccess: (q) => navigate(`/invoices/quotes/${q.id}`),
    onError: (err) => setError(apiErrorMessage(err)),
  });
  return (
    <form onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="panel-form">
        <div className="field"><label htmlFor="cot-cliente">Cliente</label>
          <select id="cot-cliente" required value={cliente} onChange={(e) => setCliente(e.target.value)}>
            <option value="">Elige un cliente</option>
            {customers.map((c) => <option key={c.id} value={c.id}>{c.legal_name}</option>)}
          </select></div>
        <div className="field"><label htmlFor="cot-titulo">Trabajo</label>
          <input id="cot-titulo" value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="Reparación de ductos" /></div>
        <div className="field"><label htmlFor="cot-vigencia">Vigente hasta</label>
          <input id="cot-vigencia" type="date" value={vigencia} onChange={(e) => setVigencia(e.target.value)} /></div>
      </div>
      <h4 className="acta-section-title">Líneas</h4>
      <LinesEditor lines={lineas} onChange={setLineas} />
      <div className="acta-actions" style={{ marginTop: "0.9rem" }}>
        <button type="button" className="acta-btn is-quiet" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="acta-btn is-primary" disabled={crear.isPending}>Crear borrador</button>
      </div>
    </form>
  );
}
