import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DataTable, PaginatedTable, RowAction } from "@/components/DataTable";
import { askText } from "@/components/ui/ConfirmDialog";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/features/auth/AuthContext";
import { toast } from "@/lib/toast";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import {
  createEntry, downloadCsv, getAllAccounts, getBalanceSheet, getIncomeStatement, getLedger, getLock, getTaxSummary, getTrialBalance,
  reverseEntry, saveAccount, setLock, syncAccounting, usd, type Account, type Entry, type StatementRow,
} from "./api";
import "./accounting.css";

const TABS = [["income", "Estado de resultados"], ["balance", "Balance general"], ["trial", "Comprobación"], ["journal", "Libro diario"],
  ["accounts", "Plan de cuentas"], ["tax", "Impuestos"]] as const;
type Tab = (typeof TABS)[number][0];

const iso = (d: Date) => d.toLocaleDateString("en-CA");
const mensaje = (e: unknown) => (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "No se pudo completar.";

/**
 * Contabilidad para reemplazar QuickBooks. Los asientos salen solos de facturas,
 * pagos, gastos, proveedores y bodega; aquí se revisan y se agrega lo que el
 * sistema no conoce (nómina, traslados entre cuentas, aportes). Base de causación.
 */
export function AccountingPage() {
  const [tab, setTab] = useState<Tab>("income");
  const [cuenta, setCuenta] = useState<string | null>(null);
  const { hasPermission } = useAuth();
  const qc = useQueryClient();
  const puede = hasPermission("accounting.manage");
  const sync = useMutation({
    mutationFn: syncAccounting,
    onSuccess: (r) => { toast(`${r.posted} asientos nuevos · ${r.reversed} reversados`); return qc.invalidateQueries({ queryKey: ["accounting"] }); },
    onError: (e) => toast(mensaje(e)),
  });
  return (
    <div className="acc-page">
      <PageHeader eyebrow="Finanzas" title="Contabilidad"
        description="Los asientos salen solos de facturas, pagos, gastos, proveedores y bodega. Aquí se revisan los estados y se agrega lo que el sistema no conoce, como la nómina."
        actions={puede ? <button type="button" className="acta-btn" disabled={sync.isPending} onClick={() => sync.mutate()}>Actualizar ahora</button> : undefined} />
      <div className="acc-tabs" role="tablist">
        {TABS.map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "is-on" : ""}
            onClick={() => { setTab(k); setCuenta(null); }}>{l}</button>
        ))}
      </div>
      {cuenta ? <LedgerView id={cuenta} onBack={() => setCuenta(null)} /> : (
        <>
          {tab === "income" && <Income onAccount={setCuenta} />}
          {tab === "balance" && <Balance onAccount={setCuenta} />}
          {tab === "trial" && <Trial onAccount={setCuenta} />}
          {tab === "journal" && <Journal puede={puede} />}
          {tab === "accounts" && <Accounts puede={puede} onAccount={setCuenta} />}
          {tab === "tax" && <Tax />}
        </>
      )}
    </div>
  );
}

function Lines({ rows, onAccount }: { rows: StatementRow[]; onAccount: (id: string) => void }) {
  if (!rows.length) return <p className="acc-note">Sin movimientos.</p>;
  return <>{rows.map((r) => (
    <button key={r.account_id} type="button" className="acc-line" onClick={() => onAccount(r.account_id)}>
      <span><small>{r.code}</small>{r.name}</span><span>{usd(r.amount)}</span>
    </button>
  ))}</>;
}
const Total = ({ label, value, net }: { label: string; value: string; net?: boolean }) => (
  <div className={`acc-line ${net ? "acc-net" : "acc-total"}`}><span>{label}</span><span>{usd(value)}</span></div>
);

function Income({ onAccount }: { onAccount: (id: string) => void }) {
  const hoy = new Date();
  const [desde, setDesde] = useState(`${hoy.getFullYear()}-01-01`);
  const [hasta, setHasta] = useState(iso(hoy));
  const { data, isError } = useQuery({ queryKey: ["accounting", "income", desde, hasta], queryFn: () => getIncomeStatement(desde, hasta), enabled: !!desde && !!hasta });
  return (
    <>
      <div className="acc-bar">
        <label>Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
        <label>Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
        <Export path="income-statement" params={{ date_from: desde, date_to: hasta }} nombre={`estado-de-resultados-${desde}-${hasta}`} />
      </div>
      {isError && <p className="form-error" role="alert">No se pudo cargar el reporte.</p>}
      {data && (
        <section className="acc-sheet" aria-label="Estado de resultados">
          <h3>Ingresos</h3><Lines rows={data.income} onAccount={onAccount} /><Total label="Total ingresos" value={data.total_income} />
          <h3>Costo de ventas</h3><Lines rows={data.cogs} onAccount={onAccount} /><Total label="Utilidad bruta" value={data.gross_profit} />
          <h3>Gastos</h3><Lines rows={data.expenses} onAccount={onAccount} /><Total label="Total gastos" value={data.total_expenses} />
          <Total label="Utilidad neta" value={data.net_income} net />
        </section>
      )}
    </>
  );
}

function Balance({ onAccount }: { onAccount: (id: string) => void }) {
  const [fecha, setFecha] = useState(iso(new Date()));
  const { data } = useQuery({ queryKey: ["accounting", "balance", fecha], queryFn: () => getBalanceSheet(fecha), enabled: !!fecha });
  return (
    <>
      <div className="acc-bar">
        <label>A la fecha<input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
        {data && <span className={data.balanced ? "acc-ok" : "acc-bad"}>{data.balanced ? "✓ Cuadra" : "No cuadra: revisar"}</span>}
        <Export path="balance-sheet" params={{ as_of: fecha }} nombre={`balance-general-${fecha}`} />
      </div>
      {data && (
        <section className="acc-sheet" aria-label="Balance general">
          <h3>Activos</h3><Lines rows={data.assets} onAccount={onAccount} /><Total label="Total activos" value={data.total_assets} />
          <h3>Pasivos</h3><Lines rows={data.liabilities} onAccount={onAccount} /><Total label="Total pasivos" value={data.total_liabilities} />
          <h3>Patrimonio</h3><Lines rows={data.equity} onAccount={onAccount} />
          <div className="acc-line"><span>Utilidad acumulada</span><span>{usd(data.retained_earnings)}</span></div>
          <Total label="Total patrimonio" value={data.total_equity} />
          <Total label="Total pasivo y patrimonio" value={data.total_liabilities_equity} net />
        </section>
      )}
    </>
  );
}

function Trial({ onAccount }: { onAccount: (id: string) => void }) {
  const [fecha, setFecha] = useState(iso(new Date()));
  const { data, isLoading } = useQuery({ queryKey: ["accounting", "trial", fecha], queryFn: () => getTrialBalance(fecha), enabled: !!fecha });
  return (
    <>
      <div className="acc-bar">
        <label>A la fecha<input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
        {data && <span className={data.balanced ? "acc-ok" : "acc-bad"}>{data.balanced ? "✓ Débitos y créditos iguales" : "No cuadra: revisar"}</span>}
      </div>
      <DataTable rows={data?.rows ?? []} isLoading={isLoading} getRowKey={(r) => r.account_id} className="billing-table" emptyMessage="Sin movimientos."
        columns={[
          { key: "cuenta", header: "Cuenta", render: (r) => <button type="button" className="acta-link" onClick={() => onAccount(r.account_id)}>{r.code} {r.name}</button> },
          { key: "tipo", header: "Tipo", render: (r) => r.account_type },
          { key: "debe", header: "Débito", className: "num", render: (r) => Number(r.debit) ? usd(r.debit) : "" },
          { key: "haber", header: "Crédito", className: "num", render: (r) => Number(r.credit) ? usd(r.credit) : "" },
        ]}
        footer={data ? ["Total", "", usd(data.total_debit), usd(data.total_credit)] : undefined} />
    </>
  );
}

function LedgerView({ id, onBack }: { id: string; onBack: () => void }) {
  const { data, isLoading } = useQuery({ queryKey: ["accounting", "ledger", id], queryFn: () => getLedger(id) });
  return (
    <>
      <div className="acc-bar">
        <button type="button" className="acta-btn" onClick={onBack}>‹ Volver</button>
        {data && <strong>{data.account.code} {data.account.name} · saldo {usd(data.closing_balance)}</strong>}
      </div>
      <DataTable rows={data?.rows ?? []} isLoading={isLoading} getRowKey={(r) => r.id} className="billing-table" emptyMessage="Sin movimientos."
        columns={[
          { key: "fecha", header: "Fecha", render: (r) => r.entry_date },
          { key: "asiento", header: "Asiento", render: (r) => r.number },
          { key: "concepto", header: "Concepto", render: (r) => r.memo },
          { key: "debe", header: "Débito", className: "num", render: (r) => Number(r.debit) ? usd(r.debit) : "" },
          { key: "haber", header: "Crédito", className: "num", render: (r) => Number(r.credit) ? usd(r.credit) : "" },
          { key: "saldo", header: "Saldo", className: "num", render: (r) => usd(r.balance) },
        ]} />
    </>
  );
}

const FUENTE: Record<string, string> = { invoice: "Factura", "invoice-payment": "Pago de factura", "supplier-invoice": "Factura de proveedor",
  "supplier-payment": "Pago a proveedor", expense: "Gasto", "expense-reimbursement": "Reembolso", warehouse: "Bodega", "extra-charge": "Cobro en obra" };

function Journal({ puede }: { puede: boolean }) {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [origen, setOrigen] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const hoy = new Date();
  const [desde, setDesde] = useState(`${hoy.getFullYear()}-01-01`);
  const [hasta, setHasta] = useState(iso(hoy));
  const lista = usePaginatedQuery<Entry>({ key: ["accounting", "entries"], path: "/accounting/entries", pageSize: 25,
    params: { q: q || undefined, source: origen || undefined, date_from: desde || undefined, date_to: hasta || undefined } });
  const reversar = useMutation({
    mutationFn: (v: { id: string; reason: string }) => reverseEntry(v.id, v.reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounting"] }),
    onError: (e) => toast(mensaje(e)),
  });
  return (
    <>
      <div className="acc-bar">
        <label>Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
        <label>Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
        <label>Origen<select value={origen} onChange={(e) => setOrigen(e.target.value)}>
          <option value="">Todos</option><option value="automatic">Automáticos</option><option value="manual">Manuales</option></select></label>
        <label>Buscar<input type="search" value={q} maxLength={80} onChange={(e) => setQ(e.target.value)} /></label>
        <div className="acc-push">
          <Export path="journal" params={{ date_from: desde, date_to: hasta }} nombre={`libro-diario-${desde}-${hasta}`} inline />
          {puede && <button type="button" className="primary-button" onClick={() => setNuevo((v) => !v)}>{nuevo ? "Cerrar" : "Nuevo asiento"}</button>}
        </div>
      </div>
      {nuevo && <EntryForm onDone={() => setNuevo(false)} />}
      <PaginatedTable list={lista} getRowKey={(e) => e.id} className="billing-table" emptyMessage="No hay asientos."
        columns={[
          { key: "fecha", header: "Fecha", render: (e) => e.entry_date },
          { key: "numero", header: "Asiento", render: (e) => e.number },
          { key: "concepto", header: "Concepto", render: (e) => (
            <div><strong>{e.memo}</strong>
              <div className="acc-subline">{e.lines.map((l, i) => (
                <div key={i}><span>{l.account_code} {l.account_name}</span><span>{Number(l.debit) ? usd(l.debit) : `(${usd(l.credit)})`}</span></div>
              ))}</div></div>
          ) },
          { key: "origen", header: "Origen", render: (e) => e.is_reversal ? "Reversa" : e.automatic ? FUENTE[e.source_type ?? ""] ?? "Automático" : "Manual" },
          { key: "total", header: "Total", className: "num", render: (e) => usd(e.total) },
          { key: "accion", header: "", render: (e) => puede && !e.automatic && !e.is_reversal && !e.reversed ? (
            <RowAction variant="danger" disabled={reversar.isPending} onClick={async () => {
              const reason = await askText({ title: `Reversar ${e.number}`, label: "Motivo", required: true, confirmLabel: "Reversar" });
              if (reason) reversar.mutate({ id: e.id, reason });
            }}>Reversar</RowAction>
          ) : e.reversed ? "Reversado" : null },
        ]} />
      {puede && <PeriodLock />}
    </>
  );
}

function EntryForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const { data: cuentas } = useQuery({ queryKey: ["accounting", "accounts-all"], queryFn: getAllAccounts });
  const vacia = () => ({ account_id: "", debit: "", credit: "" });
  const [fecha, setFecha] = useState(iso(new Date()));
  const [memo, setMemo] = useState("");
  const [lineas, setLineas] = useState([vacia(), vacia()]);
  const [error, setError] = useState<string | null>(null);
  const suma = (k: "debit" | "credit") => lineas.reduce((a, l) => a + Math.round(Number(l[k] || 0) * 100), 0) / 100;
  const cuadra = suma("debit") > 0 && suma("debit") === suma("credit");
  const guardar = useMutation({
    mutationFn: () => createEntry({ entry_date: fecha, memo, lines: lineas.map((l) => ({ account_id: l.account_id, debit: l.debit || "0", credit: l.credit || "0" })) }),
    onSuccess: () => { onDone(); return qc.invalidateQueries({ queryKey: ["accounting"] }); },
    onError: (e) => setError(mensaje(e)),
  });
  const set = (i: number, patch: Partial<ReturnType<typeof vacia>>) => setLineas(lineas.map((l, n) => (n === i ? { ...l, ...patch } : l)));
  return (
    <form className="acc-box" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <p className="acc-note">Para lo que el sistema no conoce: nómina, traslados entre cuentas, aportes, pago de la tarjeta o saldos iniciales.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acc-bar">
        <label>Fecha<input type="date" required value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
        <label style={{ flex: "1 1 16rem" }}>Concepto<input required maxLength={500} value={memo} onChange={(e) => setMemo(e.target.value)} /></label>
      </div>
      <div className="acc-entry-lines">
        {lineas.map((l, i) => (
          <div className="acc-entry-line" key={i}>
            <select aria-label="Cuenta" required value={l.account_id} onChange={(e) => set(i, { account_id: e.target.value })}>
              <option value="">Cuenta…</option>
              {(cuentas ?? []).filter((c) => c.active).map((c) => <option key={c.id} value={c.id}>{c.code} {c.name}</option>)}
            </select>
            <input aria-label="Débito" placeholder="Débito" type="number" min="0" step="0.01" value={l.debit} onChange={(e) => set(i, { debit: e.target.value, credit: "" })} />
            <input aria-label="Crédito" placeholder="Crédito" type="number" min="0" step="0.01" value={l.credit} onChange={(e) => set(i, { credit: e.target.value, debit: "" })} />
            <button type="button" className="acta-btn is-quiet" aria-label="Quitar línea" disabled={lineas.length <= 2} onClick={() => setLineas(lineas.filter((_, n) => n !== i))}>✕</button>
          </div>
        ))}
      </div>
      <div className="acc-actions">
        <button type="button" className="acta-btn is-line" onClick={() => setLineas([...lineas, vacia()])}>+ Línea</button>
        <span className={cuadra ? "acc-ok" : "acc-bad"}>Débitos {usd(suma("debit"))} · Créditos {usd(suma("credit"))}</span>
        <button type="submit" className="primary-button" disabled={!cuadra || guardar.isPending}>Registrar asiento</button>
      </div>
    </form>
  );
}

function PeriodLock() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["accounting", "lock"], queryFn: getLock });
  const [fecha, setFecha] = useState("");
  const guardar = useMutation({
    mutationFn: (v: string | null) => setLock(v),
    onSuccess: () => { setFecha(""); return qc.invalidateQueries({ queryKey: ["accounting"] }); },
    onError: (e) => toast(mensaje(e)),
  });
  return (
    <section className="acc-box" aria-label="Cierre contable">
      <strong>Cierre contable</strong>
      <p className="acc-note">{data?.locked_through ? `Cerrado hasta el ${data.locked_through}. ` : "Sin períodos cerrados. "}
        Nada se registra con fecha cerrada: lo que cambie después cae en el primer día abierto.</p>
      <div className="acc-bar">
        <label>Cerrar hasta<input type="date" value={fecha} max={iso(new Date())} onChange={(e) => setFecha(e.target.value)} /></label>
        <button type="button" className="acta-btn" disabled={!fecha || guardar.isPending} onClick={() => guardar.mutate(fecha)}>Cerrar período</button>
        {data?.locked_through && <button type="button" className="acta-btn is-quiet" disabled={guardar.isPending} onClick={() => guardar.mutate(null)}>Reabrir</button>}
      </div>
    </section>
  );
}

function Accounts({ puede, onAccount }: { puede: boolean; onAccount: (id: string) => void }) {
  const qc = useQueryClient();
  const lista = usePaginatedQuery<Account>({ key: ["accounting", "accounts"], path: "/accounting/accounts", pageSize: 50 });
  const [codigo, setCodigo] = useState("");
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState("expense");
  const listo = () => qc.invalidateQueries({ queryKey: ["accounting"] });
  const crear = useMutation({
    mutationFn: () => saveAccount({ code: codigo.trim(), name: nombre.trim(), account_type: tipo }),
    onSuccess: () => { setCodigo(""); setNombre(""); return listo(); },
    onError: (e) => toast(mensaje(e)),
  });
  const cambiar = useMutation({
    mutationFn: (v: { id: string; body: Partial<Account> }) => saveAccount(v.body, v.id),
    onSuccess: listo,
    onError: (e) => toast(mensaje(e)),
  });
  return (
    <>
      {puede && (
        <form className="acc-bar" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
          <label>Código<input required maxLength={20} value={codigo} onChange={(e) => setCodigo(e.target.value)} /></label>
          <label>Nombre<input required maxLength={120} value={nombre} onChange={(e) => setNombre(e.target.value)} /></label>
          <label>Tipo<select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="asset">Activo</option><option value="liability">Pasivo</option><option value="equity">Patrimonio</option>
            <option value="income">Ingreso</option><option value="cogs">Costo de ventas</option><option value="expense">Gasto</option></select></label>
          <button type="submit" className="acta-btn" disabled={crear.isPending}>Agregar cuenta</button>
        </form>
      )}
      <PaginatedTable list={lista} getRowKey={(a) => a.id} className="billing-table" emptyMessage="Sin cuentas."
        columns={[
          { key: "codigo", header: "Código", render: (a) => a.code },
          { key: "nombre", header: "Nombre", render: (a) => <button type="button" className="acta-link" onClick={() => onAccount(a.id)}>{a.name}</button> },
          { key: "tipo", header: "Tipo", render: (a) => a.account_type_label },
          { key: "renglon", header: "Renglón de impuestos", render: (a) => a.tax_category ?? "—" },
          { key: "uso", header: "Uso", render: (a) => a.system_key ? "Asientos automáticos" : a.active ? "Manual" : "Inactiva" },
          { key: "accion", header: "", render: (a) => !puede ? null : (
            <div className="row-actions">
              <RowAction onClick={async () => {
                const n = await askText({ title: `Renombrar ${a.code}`, label: `Nombre (hoy: ${a.name})`, required: true, confirmLabel: "Guardar" });
                if (n) cambiar.mutate({ id: a.id, body: { name: n } });
              }}>Renombrar</RowAction>
              {!a.system_key && <RowAction onClick={() => cambiar.mutate({ id: a.id, body: { active: !a.active } })}>{a.active ? "Desactivar" : "Activar"}</RowAction>}
            </div>
          ) },
        ]} />
    </>
  );
}

function Tax() {
  const actual = new Date().getFullYear();
  const [anio, setAnio] = useState(actual);
  const { data, isLoading } = useQuery({ queryKey: ["accounting", "tax", anio], queryFn: () => getTaxSummary(anio) });
  return (
    <>
      <div className="acc-bar">
        <label>Año<select value={anio} onChange={(e) => setAnio(Number(e.target.value))}>
          {[actual, actual - 1, actual - 2].map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
        <Export path="tax-summary" params={{ year: anio }} nombre={`impuestos-${anio}`} />
      </div>
      <p className="acc-note">Es el insumo para el contador: no presenta nada ante el IRS ni ante el estado. Los renglones son orientativos y el contador los valida según el tipo de empresa.</p>
      <DataTable rows={data?.lines ?? []} isLoading={isLoading} getRowKey={(l) => `${l.group}-${l.tax_category}`} className="billing-table" emptyMessage="Sin movimientos ese año."
        columns={[
          { key: "grupo", header: "Grupo", render: (l) => l.group },
          { key: "renglon", header: "Renglón", render: (l) => <div><strong>{l.tax_category}</strong><div className="acc-subline">{l.accounts.join(" · ")}</div></div> },
          { key: "valor", header: "Valor", className: "num", render: (l) => usd(l.amount) },
        ]}
        footer={data ? ["Utilidad neta", "", usd(data.net_income)] : undefined} />
      <section className="acc-box" aria-label="1099-NEC">
        <strong>Proveedores para el 1099-NEC de {anio}</strong>
        <p className="acc-note">Pagado desde {data ? usd(data.threshold_1099) : "—"} en el año, sin contar tarjeta (la reporta el procesador). El contador define quién va: las corporaciones suelen estar exentas.</p>
        <DataTable rows={data?.contractors_1099 ?? []} isLoading={isLoading} getRowKey={(c) => c.supplier_id} className="billing-table" emptyMessage="Ningún proveedor llega al umbral."
          columns={[
            { key: "nombre", header: "Proveedor", render: (c) => c.name },
            { key: "tin", header: "TIN", render: (c) => c.tax_id ?? "—" },
            { key: "pagado", header: "Pagado", className: "num", render: (c) => usd(c.total_paid) },
            { key: "falta", header: "Falta", render: (c) => c.missing.length ? <span className="acc-bad">{c.missing.join(", ")}</span> : "Completo" },
          ]} />
      </section>
    </>
  );
}

function Export({ path, params, nombre, inline }: { path: string; params: Record<string, string | number>; nombre: string; inline?: boolean }) {
  const { hasPermission } = useAuth();
  if (!hasPermission("accounting.export")) return null;
  const boton = <button type="button" className="acta-btn" onClick={() => void downloadCsv(path, params, nombre).catch((e) => toast(mensaje(e)))}>Exportar para el contador (CSV)</button>;
  return inline ? boton : <div className="acc-push">{boton}</div>;
}
