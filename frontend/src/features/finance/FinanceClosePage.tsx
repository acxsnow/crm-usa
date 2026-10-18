import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "./finance.css";
import { PaginationControls } from "@/components/PaginationControls";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { listPrograms, programKeys } from "@/features/programs/api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import {
  ignoreLine,
  importStatement,
  lineCandidates,
  matchLine,
  money,
  profitabilityReport,
  reconSummary,
  unmatchLine,
  type BankLine,
} from "./api";
import { Tabs, fecha } from "./common";

type Tab = "profit" | "recon";

/** Rentabilidad por proyecto y conciliación bancaria (Flujo Operativo §4.5). */
export function FinanceClosePage() {
  const { hasPermission } = useAuth();
  const tabs: [Tab, string][] = [
    ...(hasPermission("profitability.read") ? [["profit", "Rentabilidad por proyecto"] as [Tab, string]] : []),
    ...(hasPermission("reconciliation.manage") ? [["recon", "Conciliación bancaria"] as [Tab, string]] : []),
  ];
  const [tab, setTab] = useState<Tab>(tabs[0]?.[0] ?? "profit");
  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Conciliación y rentabilidad</h1>
          <p>Cuánto dejó cada instalación y si lo registrado cuadra con el banco.</p>
        </div>
      </header>
      {tabs.length > 1 && <Tabs tabs={tabs} value={tab} onChange={setTab} />}
      {tab === "profit" ? <Profit /> : <Recon />}
    </div>
  );
}

function Profit() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [programa, setPrograma] = useState("");
  const { data: programas } = useQuery({ queryKey: programKeys.list, queryFn: listPrograms });
  const { data, isLoading } = useQuery({
    queryKey: ["profitability", desde, hasta, programa],
    queryFn: () => profitabilityReport({ date_from: desde || undefined, date_to: hasta || undefined, program_id: programa || undefined }),
  });
  const t = data?.totals;
  return (
    <article className="acta">
      <div className="notices-toolbar fin-filters">
        <label className="notices-hint">Instalación cerrada desde <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
        <label className="notices-hint">hasta <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
        <select aria-label="Programa" value={programa} onChange={(e) => setPrograma(e.target.value)}>
          <option value="">Todos los programas</option>
          {(programas ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>
      {t && (
        <div className="fin-kpis">
          <div className="fin-kpi"><small>Esperado</small><strong>{money(t.expected as string)}</strong></div>
          <div className="fin-kpi"><small>Cobrado</small><strong>{money(t.collected as string)}</strong></div>
          <div className="fin-kpi"><small>Costos</small><strong>{money(t.costs as string)}</strong></div>
          <div className={`fin-kpi is-total${Number(t.margin) < 0 ? " is-alert" : ""}`}><small>Margen</small>
            <strong>{money(t.margin as string)}{t.margin_pct !== null ? ` · ${t.margin_pct}%` : ""}</strong></div>
        </div>
      )}
      {isLoading ? <p className="acta-empty">Cargando…</p> : (data?.rows ?? []).length === 0 ? <p className="acta-empty">Sin proyectos en el periodo.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Proyecto</th><th>Esperado</th><th>Cobrado</th><th>Costos</th><th>Margen</th></tr></thead>
          <tbody>{data!.rows.map((r) => (
            <tr key={r.project_id} className={Number(r.margin) < 0 ? "fin-overdue" : ""}>
              <td><Link to={`/projects/${r.project_id}`} className="acta-link"><strong>{r.title}</strong></Link>
                <small>{[r.case_number, r.program, r.completed_date ? `cerrada ${fecha(r.completed_date)}` : "sin cerrar"].filter(Boolean).join(" · ")}</small></td>
              <td className="mono">{money(r.expected)}</td>
              <td className="mono">{money(r.collected)}</td>
              <td className="mono">{money(r.costs)}
                <small>{Object.entries(r.cost_breakdown).filter(([, v]) => Number(v) > 0).map(([k, v]) => `${data!.cost_labels[k]} ${money(v)}`).join(" · ")}</small></td>
              <td className="mono"><strong>{money(r.margin)}</strong>{r.margin_pct !== null && <small>{r.margin_pct}%</small>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      <p className="notices-hint">Margen = cobrado − (facturas de proveedor asignadas al proyecto, con su parte de impuestos y envío, + gastos de campo aprobados). La comisión del vendedor no está incluida.</p>
    </article>
  );
}

function Recon() {
  const qc = useQueryClient();
  const { data: resumen } = useQuery({ queryKey: ["recon-summary"], queryFn: reconSummary });
  const [estado, setEstado] = useState("unmatched");
  const lineas = usePaginatedQuery<BankLine>({ key: ["recon-lines"], path: "/reconciliation/lines", pageSize: 25, params: { status: estado || undefined } });
  const [cuenta, setCuenta] = useState("Cuenta principal");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refrescar = () => { qc.invalidateQueries({ queryKey: ["recon-lines"] }); qc.invalidateQueries({ queryKey: ["recon-summary"] }); };
  const importar = useMutation({ mutationFn: () => importStatement(cuenta, archivo!),
    onSuccess: (r) => { setError(null); setArchivo(null); setMsg(`${r.lines} movimientos importados; ${r.auto_matched} se conciliaron solos.${r.invalid.length ? ` Filas no leídas: ${r.invalid.join(", ")}` : ""}`); refrescar(); },
    onError: (e) => { setMsg(null); setError(apiErrorMessage(e)); }, meta: { silent: true } });
  return (
    <>
      <article className="acta">
        <form className="fin-inline fin-import" onSubmit={(e) => { e.preventDefault(); importar.mutate(); }}>
          <input aria-label="Cuenta" value={cuenta} onChange={(e) => setCuenta(e.target.value)} placeholder="Cuenta" />
          <input aria-label="Extracto CSV" type="file" accept=".csv,text/csv" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
          <button type="submit" className="acta-btn is-primary" disabled={!archivo || importar.isPending}>{importar.isPending ? "Importando…" : "Importar extracto"}</button>
        </form>
        <p className="notices-hint">CSV del banco con fecha, descripción y monto (o débito y crédito). Cada movimiento se cruza con los pagos registrados del mismo monto y fecha cercana (±5 días).</p>
        {error && <p className="form-error" role="alert">{error}</p>}
        {msg && <p className="info-banner" role="status">{msg}</p>}
        {resumen && (
          <div className="fin-kpis">
            <div className={`fin-kpi${resumen.unmatched ? " is-alert" : ""}`}><small>Por conciliar</small><strong>{resumen.unmatched}</strong></div>
            <div className="fin-kpi"><small>Conciliados</small><strong>{resumen.matched}</strong></div>
            <div className="fin-kpi"><small>Otros (comisiones, traspasos)</small><strong>{resumen.ignored}</strong></div>
          </div>
        )}
      </article>
      <article className="acta">
        <div className="notices-toolbar">
          <select aria-label="Estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="unmatched">Por conciliar</option><option value="matched">Conciliados</option>
            <option value="ignored">Otros</option><option value="">Todos</option>
          </select>
        </div>
        {lineas.items.length === 0 ? <p className="acta-empty">Nada aquí.</p> : (
          <ul className="fin-bank">{lineas.items.map((l) => <BankLineItem key={l.id} l={l} onDone={refrescar} />)}</ul>
        )}
        <PaginationControls {...lineas.controls} />
      </article>
    </>
  );
}

function BankLineItem({ l, onDone }: { l: BankLine; onDone: () => void }) {
  const [abierta, setAbierta] = useState(false);
  const [nota, setNota] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { data: cands } = useQuery({ queryKey: ["recon-cands", l.id], queryFn: () => lineCandidates(l.id), enabled: abierta && l.status === "unmatched" });
  const ok = () => { setError(null); setAbierta(false); onDone(); };
  const casar = useMutation({ mutationFn: (c: { type: string; id: string }) => matchLine(l.id, c.type, c.id), onSuccess: ok, onError: (e) => setError(apiErrorMessage(e)) });
  const ignorar = useMutation({ mutationFn: () => ignoreLine(l.id, nota), onSuccess: ok, onError: (e) => setError(apiErrorMessage(e)) });
  const deshacer = useMutation({ mutationFn: () => unmatchLine(l.id), onSuccess: ok, onError: (e) => setError(apiErrorMessage(e)) });
  const entra = Number(l.amount) > 0;
  return (
    <li className={`fin-bank-line is-${l.status}`}>
      <div className="fin-bank-head">
        <span><strong>{l.description}</strong><small>{fecha(l.date)}{l.reference ? ` · ${l.reference}` : ""}</small></span>
        <span className={`mono ${entra ? "fin-in" : "fin-out"}`}>{entra ? "+" : "−"}{money(Math.abs(Number(l.amount)))}</span>
      </div>
      {l.status === "matched" && <small>✓ {l.matched_label}{l.auto_matched ? " (automático)" : ""} · <button type="button" className="acta-link" onClick={() => deshacer.mutate()}>Deshacer</button></small>}
      {l.status === "ignored" && <small>Otro: {l.notes} · <button type="button" className="acta-link" onClick={() => deshacer.mutate()}>Deshacer</button></small>}
      {l.status === "unmatched" && (abierta ? (
        <div className="fin-cands">
          {cands === undefined ? <small>Buscando…</small> : cands.length === 0 ? <small>No hay un pago registrado de {money(Math.abs(Number(l.amount)))} cerca de esa fecha. Si debe estar, regístralo; si no, márcalo como otro.</small> : (
            <ul>{cands.map((c) => (
              <li key={c.id}><span>{c.label} · {fecha(c.date)} · {money(c.amount)}</span>
                <button type="button" className="acta-btn is-line" onClick={() => casar.mutate(c)}>Conciliar</button></li>))}</ul>
          )}
          <form className="fin-inline" onSubmit={(e) => { e.preventDefault(); ignorar.mutate(); }}>
            <input aria-label="Qué es" placeholder="Es otra cosa (comisión, traspaso…)" value={nota} onChange={(e) => setNota(e.target.value)} />
            <button type="submit" className="acta-link" disabled={!nota.trim()}>Marcar como otro</button>
            <button type="button" className="acta-link" onClick={() => setAbierta(false)}>Cerrar</button>
          </form>
        </div>
      ) : <button type="button" className="acta-link" onClick={() => setAbierta(true)}>Conciliar…</button>)}
      {error && <p className="form-error" role="alert">{error}</p>}
    </li>
  );
}
