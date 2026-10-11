import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { listCustomers } from "@/features/crm/api";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import type { LineInput, QuoteStatus } from "@/types/billing";
import { billingKeys, createQuote, getQuotesSummary, listQuotesPage, money, shortDay } from "./billingApi";
import { PaginationControls } from "@/components/PaginationControls";
import { LinesEditor, emptyLine } from "./LinesEditor";

// `statuses` vacío = todas. Se filtra en el servidor: la lista va paginada.
const FILTROS: { key: string; label: string; statuses: QuoteStatus[] }[] = [
  { key: "all", label: "Todas", statuses: [] },
  { key: "draft", label: "Borradores", statuses: ["draft"] },
  { key: "sent", label: "Esperando respuesta", statuses: ["sent"] },
  { key: "accepted", label: "Aceptadas", statuses: ["accepted"] },
  { key: "closed", label: "No aceptadas o vencidas", statuses: ["rejected", "expired"] },
];
const PAGE_SIZE = 20;

/** Trabajo particular: cotizaciones vigentes y crear una nueva. */
export function QuotesTab() {
  const [nueva, setNueva] = useState(false);
  const [filtro, setFiltro] = useState("all");
  const [page, setPage] = useState(1);
  const activo = FILTROS.find((f) => f.key === filtro)!;
  // Bajo la clave `billingKeys.quotes` para que crear o editar una cotización refresque todo.
  const { data, isLoading } = useQuery({
    queryKey: [...billingKeys.quotes, "page", filtro, page],
    queryFn: () => listQuotesPage(page, PAGE_SIZE, activo.statuses.join(",") || undefined),
  });
  const { data: resumen } = useQuery({ queryKey: [...billingKeys.quotes, "summary"], queryFn: getQuotesSummary });
  const { data: customers } = useQuery({ queryKey: ["customers-all"], queryFn: listCustomers });
  const nombre = (id: string) => customers?.find((c) => c.id === id)?.legal_name ?? "Cliente";
  const visibles = data?.items ?? [];
  const contar = (st: QuoteStatus[]) =>
    Object.entries(resumen ?? {}).filter(([s]) => st.length === 0 || st.includes(s as QuoteStatus))
      .reduce((a, [, r]) => ({ count: a.count + r.count, total: a.total + r.total }), { count: 0, total: 0 });
  const totalGeneral = contar([]).count;
  const elegir = (key: string) => { setFiltro(key); setPage(1); };

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
              const grupo = contar(st as QuoteStatus[]);
              return (
                <div key={label}><dt>{label}</dt>
                  <dd className={`money${st[0] === "accepted" && grupo.count ? " is-ok" : ""}`}>{money(grupo.total)}</dd>
                  <small>{grupo.count} {grupo.count === 1 ? "cotización" : "cotizaciones"}</small></div>
              );
            })}
          </dl>
        </header>
        <div className="billing-pills" role="group" aria-label="Filtrar por estado">
          {FILTROS.map((f) => (
            <button key={f.key} type="button" aria-pressed={filtro === f.key}
              className={`billing-pill${filtro === f.key ? " is-on" : ""}`} onClick={() => elegir(f.key)}>
              {f.label} <span>{contar(f.statuses).count}</span>
            </button>
          ))}
        </div>
        {isLoading ? <p className="acta-empty">Cargando…</p> : visibles.length === 0 ? (
          <p className="acta-empty">{totalGeneral ? "Ninguna cotización en este estado." : "Todavía no hay cotizaciones. Crea la primera con «Nueva cotización»."}</p>
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
        {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
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
