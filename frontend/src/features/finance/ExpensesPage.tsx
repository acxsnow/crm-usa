import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "./finance.css";
import { PaginationControls } from "@/components/PaginationControls";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import {
  createExpense,
  deleteExpense,
  expenseCatalogs,
  money,
  openFile,
  reimburseExpense,
  reviewExpense,
  today,
  type Expense,
} from "./api";
import { ProjectPicker, Tabs, fecha } from "./common";

type Tab = "mine" | "review" | "all";
const CHIP: Record<Expense["status"], string> = { submitted: "is-preparing", approved: "is-accepted", rejected: "is-rejected", reimbursed: "is-paid" };

/**
 * Gastos de campo. El técnico o vendedor registra el gasto con la foto del
 * recibo (desde el celular); Contabilidad lo aprueba o rechaza con motivo y
 * marca el reembolso. Nadie aprueba lo propio.
 */
export function ExpensesPage() {
  const { hasPermission } = useAuth();
  const propios = hasPermission("expenses.create_own");
  const aprueba = hasPermission("expenses.approve");
  const todos = hasPermission("expenses.read_all") || aprueba;
  const tabs: [Tab, string][] = [
    ...(propios ? [["mine", "Mis gastos"] as [Tab, string]] : []),
    ...(aprueba ? [["review", "Por revisar"] as [Tab, string]] : []),
    ...(todos ? [["all", "Todos"] as [Tab, string]] : []),
  ];
  const [tab, setTab] = useState<Tab>(tabs[0]?.[0] ?? "mine");
  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Gastos de campo</h1>
          <p>Gasolina, viáticos y compras menores del trabajo en campo, con su recibo.</p>
        </div>
      </header>
      {tabs.length > 1 && <Tabs tabs={tabs} value={tab} onChange={setTab} />}
      {tab === "mine" && <MyExpenses />}
      {tab === "review" && <ExpenseList key="review" status="submitted" review />}
      {tab === "all" && <ExpenseList key="all" />}
    </div>
  );
}

function MyExpenses() {
  const qc = useQueryClient();
  const { data: cat } = useQuery({ queryKey: ["expense-catalogs"], queryFn: expenseCatalogs, staleTime: Infinity });
  const lista = usePaginatedQuery<Expense>({ key: ["expenses", "mine"], path: "/expenses/mine", pageSize: 15 });
  const vacio = { expense_date: today(), category: "fuel", amount: "", description: "", payment_method: "own_money", project_id: null as string | null };
  const [f, setF] = useState(vacio);
  const [recibo, setRecibo] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const crear = useMutation({
    mutationFn: () => createExpense(f, recibo!),
    onSuccess: () => { setF(vacio); setRecibo(null); setError(null); setAviso(null); qc.invalidateQueries({ queryKey: ["expenses"] }); },
    onError: (e) => { setAviso(null); setError(apiErrorMessage(e)); },
    meta: { successMessage: "Gasto enviado a revisión." },
  });
  const borrar = useMutation({ mutationFn: deleteExpense, onSuccess: () => qc.invalidateQueries({ queryKey: ["expenses"] }) });
  return (
    <div className="fin-grid">
      <article className="acta">
        <h2 className="fin-h2">Registrar un gasto</h2>
        <form className="fin-form" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
          <div className="fin-row">
            <div className="form-field"><label className="form-label" htmlFor="ex-date">Fecha</label>
              <input id="ex-date" type="date" max={today()} value={f.expense_date} onChange={(e) => setF({ ...f, expense_date: e.target.value })} required /></div>
            <div className="form-field"><label className="form-label" htmlFor="ex-amount">Monto (USD)</label>
              <input id="ex-amount" inputMode="decimal" placeholder="0.00" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} required /></div>
          </div>
          <div className="fin-row">
            <div className="form-field"><label className="form-label" htmlFor="ex-cat">Categoría</label>
              <select id="ex-cat" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
                {Object.entries(cat?.categories ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div className="form-field"><label className="form-label" htmlFor="ex-pay">Pagado con</label>
              <select id="ex-pay" value={f.payment_method} onChange={(e) => setF({ ...f, payment_method: e.target.value })}>
                {Object.entries(cat?.payment_methods ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
          </div>
          <div className="form-field"><label className="form-label" htmlFor="ex-desc">Descripción</label>
            <input id="ex-desc" value={f.description} maxLength={500} placeholder="Ej.: gasolina ida y vuelta a Sunrise Park" onChange={(e) => setF({ ...f, description: e.target.value })} required /></div>
          <ProjectPicker id="ex-proj" value={f.project_id} onChange={(id) => setF({ ...f, project_id: id })} />
          <div className="form-field"><label className="form-label" htmlFor="ex-rec">Foto o PDF del recibo</label>
            <input id="ex-rec" type="file" accept="image/*,application/pdf" capture="environment" onChange={(e) => setRecibo(e.target.files?.[0] ?? null)} required /></div>
          {error && <p className="form-error" role="alert">{error}</p>}
          {aviso && <p className="info-banner" role="status">{aviso}</p>}
          <button type="submit" className="acta-btn is-primary fin-submit" disabled={crear.isPending || !recibo || !f.amount || f.description.trim().length < 3}>
            {crear.isPending ? "Enviando…" : "Enviar gasto"}</button>
        </form>
      </article>
      <article className="acta">
        <h2 className="fin-h2">Mis gastos</h2>
        {lista.items.length === 0 ? <p className="acta-empty">Todavía no registras gastos.</p> : (
          <ul className="fin-cards">
            {lista.items.map((g) => (
              <li key={g.id}>
                <div className="fin-card-head"><strong>{money(g.amount)} · {g.category_label}</strong>
                  <span className={`billing-chip ${CHIP[g.status]}`}>{cat?.statuses[g.status] ?? g.status}</span></div>
                <span>{g.description}</span>
                <small>{fecha(g.expense_date)}{g.project_title ? ` · ${g.project_title}` : ""} · {g.payment_label}</small>
                {g.status === "rejected" && g.review_notes && <p className="fin-note is-bad">Rechazado: {g.review_notes}</p>}
                {g.status === "reimbursed" && <small>Reembolsado el {fecha(g.reimbursed_at)}{g.reimbursement_reference ? ` · ${g.reimbursement_reference}` : ""}</small>}
                <div className="acta-actions">
                  <button type="button" className="acta-link" onClick={() => openFile(`/expenses/${g.id}/receipt`)}>Ver recibo</button>
                  {g.status === "submitted" && <button type="button" className="acta-link fin-danger" onClick={() => { if (window.confirm("¿Borrar este gasto?")) borrar.mutate(g.id); }}>Borrar</button>}
                </div>
              </li>
            ))}
          </ul>
        )}
        <PaginationControls {...lista.controls} />
      </article>
    </div>
  );
}

function ExpenseList({ status: fijo, review = false }: { status?: string; review?: boolean }) {
  const qc = useQueryClient();
  const { hasPermission, user } = useAuth();
  const { data: cat } = useQuery({ queryKey: ["expense-catalogs"], queryFn: expenseCatalogs, staleTime: Infinity });
  const [estado, setEstado] = useState(fijo ?? "");
  const lista = usePaginatedQuery<Expense>({ key: ["expenses", "all"], path: "/expenses", pageSize: 20, params: { status: estado || undefined } });
  const [rechazo, setRechazo] = useState<{ id: string; nota: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refrescar = () => { setError(null); setRechazo(null); qc.invalidateQueries({ queryKey: ["expenses"] }); };
  const revisar = useMutation({ mutationFn: (a: { id: string; ok: boolean; nota?: string }) => reviewExpense(a.id, a.ok, a.nota),
    onSuccess: refrescar, onError: (e) => setError(apiErrorMessage(e)) });
  const reembolsar = useMutation({ mutationFn: (id: string) => reimburseExpense(id, today(), window.prompt("Referencia del reembolso (Zelle, cheque…)") ?? undefined),
    onSuccess: refrescar, onError: (e) => setError(apiErrorMessage(e)) });
  const total = lista.items.reduce((s, g) => s + Number(g.amount), 0);
  return (
    <article className="acta">
      {!review && (
        <div className="notices-toolbar">
          <select aria-label="Estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="">Todos los estados</option>
            {Object.entries(cat?.statuses ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <span className="notices-hint">En esta página: {money(total)}</span>
        </div>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      {lista.items.length === 0 ? <p className="acta-empty">{review ? "No hay gastos por revisar." : "Sin gastos."}</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Fecha</th><th>Persona</th><th>Gasto</th><th>Monto</th><th>Estado</th><th /></tr></thead>
          <tbody>
            {lista.items.map((g) => (
              <tr key={g.id}>
                <td>{fecha(g.expense_date)}</td>
                <td>{g.user_name}</td>
                <td><strong>{g.category_label}</strong><small>{g.description}{g.project_title ? ` · ${g.project_title}` : ""}</small>
                  <small>{g.payment_label}</small></td>
                <td className="mono">{money(g.amount)}</td>
                <td><span className={`billing-chip ${CHIP[g.status]}`}>{cat?.statuses[g.status] ?? g.status}</span>
                  {g.review_notes && <small>{g.review_notes}</small>}{g.reviewed_by && <small>por {g.reviewed_by}</small>}</td>
                <td className="fin-actions">
                  <button type="button" className="acta-link" onClick={() => openFile(`/expenses/${g.id}/receipt`)}>Recibo</button>
                  {g.status === "submitted" && hasPermission("expenses.approve") && g.user_id !== user?.id && (
                    rechazo?.id === g.id ? (
                      <form className="fin-inline" onSubmit={(e) => { e.preventDefault(); revisar.mutate({ id: g.id, ok: false, nota: rechazo.nota }); }}>
                        <input aria-label="Motivo del rechazo" placeholder="Motivo" value={rechazo.nota} onChange={(e) => setRechazo({ id: g.id, nota: e.target.value })} autoFocus />
                        <button type="submit" className="acta-link fin-danger" disabled={!rechazo.nota.trim()}>Rechazar</button>
                      </form>
                    ) : (<>
                      <button type="button" className="acta-btn is-line" onClick={() => revisar.mutate({ id: g.id, ok: true })}>Aprobar</button>
                      <button type="button" className="acta-link fin-danger" onClick={() => setRechazo({ id: g.id, nota: "" })}>Rechazar</button>
                    </>)
                  )}
                  {g.status === "approved" && g.payment_method === "own_money" && (hasPermission("payables.manage") || hasPermission("expenses.approve")) && (
                    <button type="button" className="acta-link" onClick={() => reembolsar.mutate(g.id)}>Marcar reembolsado</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      <PaginationControls {...lista.controls} />
    </article>
  );
}
