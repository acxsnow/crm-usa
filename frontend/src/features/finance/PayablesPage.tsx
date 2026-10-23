import { useEffect, useState } from "react";
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
  approveInvoice,
  createInvoice,
  downloadFile,
  getFinanceSettings,
  getSupplier,
  importSuppliers,
  money,
  openFile,
  openInvoices,
  payablesAging,
  payablesCatalogs,
  putFinanceSettings,
  recordPayment,
  saveSupplier,
  scheduleInvoice,
  today,
  uploadSupplierDocument,
  voidInvoice,
  type FinanceSettings,
  type InvoiceLine,
  type Supplier,
  type SupplierInvoice,
  type SupplierPayment,
} from "./api";
import { ProjectPicker, Tabs, fecha } from "./common";
import { askText } from "@/components/ui/ConfirmDialog";

type Tab = "invoices" | "payments" | "suppliers" | "aging" | "settings";
const CHIP: Record<SupplierInvoice["status"], string> = {
  pending_approval: "is-preparing", approved: "is-submitted", partially_paid: "is-partial", paid: "is-paid", void: "is-void",
};
const CAPACIDAD: Record<string, string> = { approve: "Autoriza pagos", accounting: "Contabilidad", paid_now: "Pagada al momento" };

/**
 * Proveedores y cuentas por pagar. Contabilidad registra facturas y pagos;
 * quien autoriza pagos (Aldo) aprueba y programa. Desde el umbral, la factura
 * necesita las dos aprobaciones (respuesta del cliente 2.1).
 */
export function PayablesPage() {
  const { hasPermission } = useAuth();
  const params = new URLSearchParams(window.location.search);
  const [tab, setTab] = useState<Tab>((params.get("tab") as Tab) || "invoices");
  const tabs: [Tab, string][] = [["invoices", "Facturas"], ["payments", "Pagos"], ["suppliers", "Proveedores"], ["aging", "Antigüedad"],
    ...(hasPermission("payables.approve") ? [["settings", "Ajustes"] as [Tab, string]] : [])];
  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Proveedores y pagos</h1>
          <p>Lo que se le debe a proveedores y contratistas: facturas, aprobaciones, pagos y vencimientos.</p>
        </div>
        {hasPermission("accounting.export") && (
          <div className="acta-actions">
            <button type="button" className="acta-btn is-quiet" onClick={() => downloadFile("/payables/export.csv", "facturas-proveedores.csv", { kind: "invoices" })}>Exportar facturas (CSV)</button>
            <button type="button" className="acta-btn is-quiet" onClick={() => downloadFile("/payables/export.csv", "pagos-proveedores.csv", { kind: "payments" })}>Exportar pagos (CSV)</button>
          </div>
        )}
      </header>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === "invoices" && <Invoices />}
      {tab === "payments" && <Payments />}
      {tab === "suppliers" && <Suppliers />}
      {tab === "aging" && <AgingView />}
      {tab === "settings" && <SettingsView />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Facturas
// ---------------------------------------------------------------------------

function Invoices() {
  const { hasPermission } = useAuth();
  const { data: cat } = useQuery({ queryKey: ["payables-catalogs"], queryFn: payablesCatalogs, staleTime: Infinity });
  const [filtro, setFiltro] = useState("open");
  const [nueva, setNueva] = useState(false);
  const params = filtro === "overdue" ? { overdue: true } : filtro === "soon" ? { status: "open", due_within_days: 7 } : { status: filtro || undefined };
  const lista = usePaginatedQuery<SupplierInvoice>({ key: ["supplier-invoices"], path: "/payables/invoices", pageSize: 20, params });
  const [abierta, setAbierta] = useState<string | null>(null);
  return (
    <>
      <article className="acta">
        <div className="notices-toolbar">
          <select aria-label="Filtro" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="open">Con saldo (por aprobar, aprobadas, parciales)</option>
            <option value="pending_approval">Por aprobar</option>
            <option value="soon">Vencen en 7 días</option>
            <option value="overdue">Vencidas</option>
            <option value="paid">Pagadas</option>
            <option value="void">Anuladas</option>
            <option value="">Todas</option>
          </select>
          {hasPermission("payables.manage") && !nueva && <button type="button" className="acta-btn is-primary" onClick={() => setNueva(true)}>Registrar factura</button>}
        </div>
        {nueva && <NewInvoice onClose={() => setNueva(false)} />}
        {lista.items.length === 0 ? <p className="acta-empty">No hay facturas con este filtro.</p> : (
          <div className="tablewrap"><table className="notices-table">
            <thead><tr><th>Proveedor · factura</th><th>Vence</th><th>Total</th><th>Saldo</th><th>Estado</th><th /></tr></thead>
            <tbody>
              {lista.items.map((i) => (
                <InvoiceRow key={i.id} inv={i} abierta={abierta === i.id} onToggle={() => setAbierta(abierta === i.id ? null : i.id)}
                  estado={cat?.invoice_statuses[i.status] ?? i.status} />
              ))}
            </tbody>
          </table></div>
        )}
        <PaginationControls {...lista.controls} />
      </article>
    </>
  );
}

function InvoiceRow({ inv, abierta, onToggle, estado }: { inv: SupplierInvoice; abierta: boolean; onToggle: () => void; estado: string }) {
  const qc = useQueryClient();
  const { data: cat } = useQuery({ queryKey: ["payables-catalogs"], queryFn: payablesCatalogs, staleTime: Infinity });
  const { hasPermission } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [prog, setProg] = useState(inv.scheduled_payment_date ?? "");
  const listo = () => { setError(null); qc.invalidateQueries({ queryKey: ["supplier-invoices"] }); qc.invalidateQueries({ queryKey: ["payables-aging"] }); };
  const aprobar = useMutation({ mutationFn: () => approveInvoice(inv.id), onSuccess: listo, onError: (e) => setError(apiErrorMessage(e)) });
  const programar = useMutation({ mutationFn: () => scheduleInvoice(inv.id, prog || null), onSuccess: listo, onError: (e) => setError(apiErrorMessage(e)) });
  const anular = useMutation({ mutationFn: (motivo: string) => voidInvoice(inv.id, motivo), onSuccess: listo, onError: (e) => setError(apiErrorMessage(e)) });
  // Solo si a esta persona le toca una de las aprobaciones que faltan.
  const puedeAprobar = inv.status === "pending_approval" && inv.approvals_missing.some((c) =>
    (c === "approve" && hasPermission("payables.approve")) || (c === "accounting" && hasPermission("payables.manage")));
  return (
    <>
      <tr className={inv.overdue_days > 0 ? "fin-overdue" : ""}>
        <td><button type="button" className="acta-link fin-rowlink" aria-expanded={abierta} onClick={onToggle}>
          <strong>{inv.supplier_name}</strong></button><small>Factura {inv.number} · {fecha(inv.invoice_date)}</small></td>
        <td>{fecha(inv.due_date)}{inv.overdue_days > 0 && <small className="notices-error">vencida hace {inv.overdue_days} días</small>}
          {inv.scheduled_payment_date && <small>pago programado {fecha(inv.scheduled_payment_date)}</small>}</td>
        <td className="mono">{money(inv.total)}</td>
        <td className="mono">{money(inv.balance)}</td>
        <td><span className={`billing-chip ${CHIP[inv.status]}`}>{estado}</span>
          {inv.approvals_missing.length > 0 && <small>Falta: {inv.approvals_missing.map((c) => CAPACIDAD[c]).join(" y ")}</small>}</td>
        <td>{puedeAprobar && <button type="button" className="acta-btn is-line" disabled={aprobar.isPending} onClick={() => aprobar.mutate()}>Aprobar</button>}</td>
      </tr>
      {(abierta || error) && (
        <tr className="fin-detail"><td colSpan={6}>
          {error && <p className="form-error" role="alert">{error}</p>}
          {abierta && <>
            <div className="tablewrap"><table className="fin-lines">
              <thead><tr><th>Detalle</th><th>Tipo</th><th>Cant.</th><th>Costo</th><th>Importe</th><th>Proyecto</th></tr></thead>
              <tbody>{inv.lines.map((l, n) => (
                <tr key={n}><td>{l.description}</td><td>{cat?.cost_categories[l.category] ?? l.category}</td><td>{l.quantity}</td><td className="mono">{money(l.unit_cost)}</td>
                  <td className="mono">{money(l.amount)}</td><td>{l.project_title ?? "General"}</td></tr>))}</tbody>
              <tfoot><tr><td colSpan={4}>Impuestos {money(inv.tax)} · Envío {money(inv.shipping)}</td><td className="mono"><strong>{money(inv.total)}</strong></td><td>Pagado {money(inv.paid)}</td></tr></tfoot>
            </table></div>
            <p className="notices-hint">Aprobaciones: {inv.approvals.length ? inv.approvals.map((a) => `${a.user_name} (${CAPACIDAD[a.capacity] ?? a.capacity}, ${fecha(a.approved_at)})`).join(" · ") : "ninguna"}
              {inv.void_reason && ` · Anulada: ${inv.void_reason}`}{inv.notes && ` · ${inv.notes}`}</p>
            <div className="acta-actions">
              {inv.has_file && <button type="button" className="acta-link" onClick={() => openFile(`/payables/invoices/${inv.id}/file`)}>Ver factura</button>}
              {hasPermission("payables.approve") && ["approved", "partially_paid"].includes(inv.status) && (
                <form className="fin-inline" onSubmit={(e) => { e.preventDefault(); programar.mutate(); }}>
                  <label className="notices-hint" htmlFor={`prog-${inv.id}`}>Programar pago</label>
                  <input id={`prog-${inv.id}`} type="date" value={prog} onChange={(e) => setProg(e.target.value)} />
                  <button type="submit" className="acta-link">Guardar</button>
                </form>
              )}
              {inv.status !== "void" && inv.paid === "0.00" && (hasPermission("payables.manage") || hasPermission("payables.approve")) && (
                <button type="button" className="acta-link fin-danger" onClick={async () => { const m = await askText({ title: "Anular", label: "Motivo de la anulación", required: true, confirmLabel: "Anular", danger: true }); if (m?.trim()) anular.mutate(m); }}>Anular</button>
              )}
            </div>
          </>}
        </td></tr>
      )}
    </>
  );
}

function NewInvoice({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { data: cat } = useQuery({ queryKey: ["payables-catalogs"], queryFn: payablesCatalogs, staleTime: Infinity });
  const proveedores = usePaginatedQuery<Supplier>({ key: ["suppliers", "select"], path: "/payables/suppliers", pageSize: 200, params: { active: true } });
  const [proveedor, setProveedor] = useState("");
  const [numero, setNumero] = useState("");
  const [fechaF, setFechaF] = useState(today());
  const [vence, setVence] = useState("");
  const [conLineas, setConLineas] = useState(true);
  const [lineas, setLineas] = useState<InvoiceLine[]>([{ description: "", category: "equipment", quantity: "1", unit_cost: "", project_id: null }]);
  const [total, setTotal] = useState("");
  const [proyecto, setProyecto] = useState<string | null>(null);
  const [impuesto, setImpuesto] = useState("");
  const [envio, setEnvio] = useState("");
  const [pagadaYa, setPagadaYa] = useState(false);
  const [metodo, setMetodo] = useState("card");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const subtotal = conLineas ? lineas.reduce((s, l) => s + Number(l.quantity || 0) * Number(l.unit_cost || 0), 0) : Number(total || 0) - Number(impuesto || 0) - Number(envio || 0);
  const totalCalc = conLineas ? subtotal + Number(impuesto || 0) + Number(envio || 0) : Number(total || 0);
  const crear = useMutation({
    mutationFn: () => createInvoice({
      supplier_id: proveedor, number: numero, invoice_date: fechaF, due_date: vence || null, notes: null,
      ...(conLineas ? { lines: lineas.filter((l) => l.description && l.unit_cost) } : { total, project_id: proyecto, category: "materials" }),
      tax: impuesto || null, shipping: envio || null, paid_now: pagadaYa, paid_method: pagadaYa ? metodo : null,
    }, archivo),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["supplier-invoices"] }); qc.invalidateQueries({ queryKey: ["payables-aging"] }); onClose(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const cambiar = (n: number, c: Partial<InvoiceLine>) => setLineas((xs) => xs.map((x, i) => (i === n ? { ...x, ...c } : x)));
  return (
    <form className="fin-form fin-box" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
      <h3 className="acta-section-title">Nueva factura de proveedor</h3>
      <div className="fin-row">
        <div className="form-field"><label className="form-label" htmlFor="ni-sup">Proveedor</label>
          <select id="ni-sup" value={proveedor} onChange={(e) => setProveedor(e.target.value)} required>
            <option value="">Elige…</option>
            {proveedores.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select></div>
        <div className="form-field"><label className="form-label" htmlFor="ni-num">Número de factura</label>
          <input id="ni-num" value={numero} onChange={(e) => setNumero(e.target.value)} required /></div>
      </div>
      <div className="fin-row">
        <div className="form-field"><label className="form-label" htmlFor="ni-date">Fecha</label>
          <input id="ni-date" type="date" value={fechaF} onChange={(e) => setFechaF(e.target.value)} required /></div>
        <div className="form-field"><label className="form-label" htmlFor="ni-due">Vence (vacío = según condiciones del proveedor)</label>
          <input id="ni-due" type="date" value={vence} onChange={(e) => setVence(e.target.value)} /></div>
      </div>
      <label className="billing-check"><input type="checkbox" checked={conLineas} onChange={(e) => setConLineas(e.target.checked)} /> Detalle por líneas (para cargar cada costo a su proyecto)</label>
      {conLineas ? (
        <div className="fin-lines-edit">
          {lineas.map((l, n) => (
            <div key={n} className="fin-line">
              <input aria-label="Detalle" placeholder="Detalle (producto o servicio)" value={l.description} onChange={(e) => cambiar(n, { description: e.target.value })} />
              <select aria-label="Tipo de costo" value={l.category} onChange={(e) => cambiar(n, { category: e.target.value })}>
                {Object.entries(cat?.cost_categories ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <input aria-label="Cantidad" inputMode="decimal" value={l.quantity} onChange={(e) => cambiar(n, { quantity: e.target.value })} />
              <input aria-label="Costo unitario" inputMode="decimal" placeholder="Costo" value={l.unit_cost} onChange={(e) => cambiar(n, { unit_cost: e.target.value })} />
              <ProjectPicker id={`ln-${n}`} label="Proyecto" value={l.project_id} onChange={(id) => cambiar(n, { project_id: id })} />
              <button type="button" className="acta-link fin-danger" onClick={() => setLineas((xs) => xs.filter((_, i) => i !== n))} disabled={lineas.length === 1}>Quitar</button>
            </div>
          ))}
          <button type="button" className="acta-btn is-quiet" onClick={() => setLineas((xs) => [...xs, { description: "", category: "materials", quantity: "1", unit_cost: "", project_id: null }])}>+ Línea</button>
        </div>
      ) : (
        <div className="fin-row">
          <div className="form-field"><label className="form-label" htmlFor="ni-total">Total de la factura</label>
            <input id="ni-total" inputMode="decimal" value={total} onChange={(e) => setTotal(e.target.value)} required /></div>
          <ProjectPicker id="ni-proj" value={proyecto} onChange={setProyecto} />
        </div>
      )}
      <div className="fin-row">
        <div className="form-field"><label className="form-label" htmlFor="ni-tax">Impuestos</label>
          <input id="ni-tax" inputMode="decimal" placeholder="0.00" value={impuesto} onChange={(e) => setImpuesto(e.target.value)} /></div>
        <div className="form-field"><label className="form-label" htmlFor="ni-ship">Envío</label>
          <input id="ni-ship" inputMode="decimal" placeholder="0.00" value={envio} onChange={(e) => setEnvio(e.target.value)} /></div>
      </div>
      <p className="notices-hint">Total: <strong>{money(totalCalc)}</strong></p>
      <div className="form-field"><label className="form-label" htmlFor="ni-file">PDF o foto de la factura (opcional)</label>
        <input id="ni-file" type="file" accept="image/*,application/pdf" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} /></div>
      <label className="billing-check"><input type="checkbox" checked={pagadaYa} onChange={(e) => setPagadaYa(e.target.checked)} /> Ya se pagó al comprar (contado o tarjeta)</label>
      {pagadaYa && (
        <select aria-label="Forma de pago" value={metodo} onChange={(e) => setMetodo(e.target.value)}>
          {Object.entries(cat?.payment_methods ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={crear.isPending || !proveedor || !numero.trim()}>{crear.isPending ? "Guardando…" : "Registrar factura"}</button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cancelar</button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Pagos
// ---------------------------------------------------------------------------

function Payments() {
  const { hasPermission } = useAuth();
  const lista = usePaginatedQuery<SupplierPayment>({ key: ["supplier-payments"], path: "/payables/payments", pageSize: 20 });
  const [nuevo, setNuevo] = useState(false);
  return (
    <article className="acta">
      <div className="notices-toolbar">
        <p className="acta-lead">La plataforma no paga: aquí se registra el pago hecho por fuera (cheque, ACH, tarjeta…).</p>
        {hasPermission("payables.manage") && !nuevo && <button type="button" className="acta-btn is-primary" onClick={() => setNuevo(true)}>Registrar pago</button>}
      </div>
      {nuevo && <NewPayment onClose={() => setNuevo(false)} />}
      {lista.items.length === 0 ? <p className="acta-empty">Sin pagos registrados.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Fecha</th><th>Proveedor</th><th>Monto</th><th>Forma</th><th>Facturas</th><th /></tr></thead>
          <tbody>{lista.items.map((p) => (
            <tr key={p.id}><td>{fecha(p.paid_on)}</td><td>{p.supplier_name}</td><td className="mono">{money(p.amount)}</td>
              <td>{p.method_label}{p.reference && <small>{p.reference}</small>}</td><td>{p.allocations.length}</td>
              <td>{p.has_file && <button type="button" className="acta-link" onClick={() => openFile(`/payables/payments/${p.id}/file`)}>Comprobante</button>}</td></tr>
          ))}</tbody>
        </table></div>
      )}
      <PaginationControls {...lista.controls} />
    </article>
  );
}

function NewPayment({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { data: cat } = useQuery({ queryKey: ["payables-catalogs"], queryFn: payablesCatalogs, staleTime: Infinity });
  const proveedores = usePaginatedQuery<Supplier>({ key: ["suppliers", "select"], path: "/payables/suppliers", pageSize: 200, params: { active: true } });
  const [proveedor, setProveedor] = useState("");
  const { data: facturas } = useQuery({ queryKey: ["open-invoices", proveedor], queryFn: () => openInvoices(proveedor), enabled: !!proveedor });
  const pagables = (facturas ?? []).filter((f) => f.status === "approved" || f.status === "partially_paid");
  const [montos, setMontos] = useState<Record<string, string>>({});
  const [fechaP, setFechaP] = useState(today());
  const [metodo, setMetodo] = useState("ach");
  const [ref, setRef] = useState("");
  const [cuenta, setCuenta] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setMontos({}); }, [proveedor]);
  const total = Object.values(montos).reduce((s, v) => s + Number(v || 0), 0);
  const guardar = useMutation({
    mutationFn: () => recordPayment({ supplier_id: proveedor, paid_on: fechaP, amount: total.toFixed(2), method: metodo, reference: ref || null,
      bank_account: cuenta || null, allocations: Object.entries(montos).filter(([, v]) => Number(v) > 0).map(([invoice_id, amount]) => ({ invoice_id, amount })) }, archivo),
    onSuccess: () => { ["supplier-payments", "supplier-invoices", "payables-aging"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); onClose(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  return (
    <form className="fin-form fin-box" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <h3 className="acta-section-title">Registrar pago</h3>
      <div className="fin-row">
        <div className="form-field"><label className="form-label" htmlFor="np-sup">Proveedor</label>
          <select id="np-sup" value={proveedor} onChange={(e) => setProveedor(e.target.value)} required>
            <option value="">Elige…</option>
            {proveedores.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select></div>
        <div className="form-field"><label className="form-label" htmlFor="np-date">Fecha del pago</label>
          <input id="np-date" type="date" max={today()} value={fechaP} onChange={(e) => setFechaP(e.target.value)} required /></div>
      </div>
      {proveedor && (pagables.length === 0 ? <p className="acta-empty">Este proveedor no tiene facturas aprobadas con saldo.</p> : (
        <div className="tablewrap"><table className="fin-lines">
          <thead><tr><th>Factura</th><th>Vence</th><th>Saldo</th><th>Pagar ahora</th></tr></thead>
          <tbody>{pagables.map((f) => (
            <tr key={f.id}><td>{f.number}</td><td>{fecha(f.due_date)}</td><td className="mono">{money(f.balance)}</td>
              <td><div className="fin-inline">
                <input aria-label={`Monto para ${f.number}`} inputMode="decimal" value={montos[f.id] ?? ""} onChange={(e) => setMontos({ ...montos, [f.id]: e.target.value })} />
                <button type="button" className="acta-link" onClick={() => setMontos({ ...montos, [f.id]: f.balance })}>Todo</button>
              </div></td></tr>
          ))}</tbody>
        </table></div>
      ))}
      <div className="fin-row">
        <div className="form-field"><label className="form-label" htmlFor="np-met">Forma de pago</label>
          <select id="np-met" value={metodo} onChange={(e) => setMetodo(e.target.value)}>
            {Object.entries(cat?.payment_methods ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></div>
        <div className="form-field"><label className="form-label" htmlFor="np-ref">Número de cheque o referencia</label>
          <input id="np-ref" value={ref} onChange={(e) => setRef(e.target.value)} /></div>
      </div>
      <div className="fin-row">
        <div className="form-field"><label className="form-label" htmlFor="np-acc">Cuenta de la que salió</label>
          <input id="np-acc" value={cuenta} placeholder="Ej.: Chase operativa" onChange={(e) => setCuenta(e.target.value)} /></div>
        <div className="form-field"><label className="form-label" htmlFor="np-file">Comprobante (opcional)</label>
          <input id="np-file" type="file" accept="image/*,application/pdf" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} /></div>
      </div>
      <p className="notices-hint">Total del pago: <strong>{money(total)}</strong></p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending || total <= 0}>{guardar.isPending ? "Guardando…" : "Registrar pago"}</button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cancelar</button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Proveedores
// ---------------------------------------------------------------------------

function Suppliers() {
  const { hasPermission } = useAuth();
  const puede = hasPermission("suppliers.manage") || hasPermission("payables.approve");
  const [q, setQ] = useState("");
  const lista = usePaginatedQuery<Supplier>({ key: ["suppliers", "list"], path: "/payables/suppliers", pageSize: 20, params: { q: q || undefined } });
  const [edit, setEdit] = useState<Partial<Supplier> | "new" | null>(null);
  const [importar, setImportar] = useState(false);
  return (
    <article className="acta">
      <div className="notices-toolbar">
        <input aria-label="Buscar proveedor" placeholder="Buscar proveedor o contacto" value={q} onChange={(e) => setQ(e.target.value)} />
        {puede && <div className="acta-actions">
          <button type="button" className="acta-btn is-quiet" onClick={() => setImportar(!importar)}>Importar CSV</button>
          <button type="button" className="acta-btn is-primary" onClick={() => setEdit("new")}>Nuevo proveedor</button>
        </div>}
      </div>
      {importar && <ImportSuppliers onClose={() => setImportar(false)} />}
      {edit && <SupplierForm initial={edit === "new" ? {} : edit} onClose={() => setEdit(null)} />}
      {lista.items.length === 0 ? <p className="acta-empty">Sin proveedores.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Proveedor</th><th>Contacto</th><th>Condiciones</th><th>Documentos</th><th>Saldo</th><th /></tr></thead>
          <tbody>{lista.items.map((s) => (
            <tr key={s.id} className={s.active ? "" : "fin-inactive"}>
              <td><strong>{s.name}</strong><small>{s.legal_name ?? ""}{s.tax_id ? ` · EIN ${s.tax_id}` : ""}</small></td>
              <td>{s.contact_name}<small>{[s.phone, s.email].filter(Boolean).join(" · ")}</small></td>
              <td>{s.payment_terms_days === 0 ? "Contado" : `Net ${s.payment_terms_days}`}</td>
              <td><small>W-9 {s.w9_on_file ? "✓" : "—"}</small>
                {s.license_expires_on && <small>Licencia vence {fecha(s.license_expires_on)}</small>}
                {s.insurance_expires_on && <small>Seguro vence {fecha(s.insurance_expires_on)}</small>}</td>
              <td className="mono">{money(s.balance)}</td>
              <td>{puede && <button type="button" className="acta-link" onClick={() => setEdit(s)}>Editar</button>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      <PaginationControls {...lista.controls} />
    </article>
  );
}

function SupplierForm({ initial, onClose }: { initial: Partial<Supplier>; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: cat } = useQuery({ queryKey: ["payables-catalogs"], queryFn: payablesCatalogs, staleTime: Infinity });
  const { data: detalle } = useQuery({ queryKey: ["supplier", initial.id], queryFn: () => getSupplier(initial.id!), enabled: !!initial.id });
  const [s, setS] = useState<Partial<Supplier>>({ payment_terms_days: 30, kinds: [], states: [], active: true, w9_on_file: false, ...initial });
  const { hasPermission } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [doc, setDoc] = useState<{ kind: string; file: File | null; expires: string }>({ kind: "w9", file: null, expires: "" });
  const guardar = useMutation({ mutationFn: () => saveSupplier(s), onSuccess: () => { qc.invalidateQueries({ queryKey: ["suppliers"] }); onClose(); },
    onError: (e) => setError(apiErrorMessage(e)) });
  const subir = useMutation({ mutationFn: () => uploadSupplierDocument(initial.id!, doc.kind, doc.file!, doc.expires || undefined),
    onSuccess: () => { setDoc({ kind: "w9", file: null, expires: "" }); qc.invalidateQueries({ queryKey: ["supplier", initial.id] }); qc.invalidateQueries({ queryKey: ["suppliers"] }); },
    onError: (e) => setError(apiErrorMessage(e)) });
  const alternar = (campo: "kinds" | "states", v: string) =>
    setS({ ...s, [campo]: (s[campo] ?? []).includes(v) ? (s[campo] ?? []).filter((x) => x !== v) : [...(s[campo] ?? []), v] });
  const txt = (campo: keyof Supplier, label: string, extra: Record<string, unknown> = {}) => (
    <div className="form-field"><label className="form-label" htmlFor={`sf-${campo}`}>{label}</label>
      <input id={`sf-${campo}`} value={(s[campo] as string) ?? ""} onChange={(e) => setS({ ...s, [campo]: e.target.value || null })} {...extra} /></div>
  );
  return (
    <form className="fin-form fin-box" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <h3 className="acta-section-title">{initial.id ? `Editar ${initial.name}` : "Nuevo proveedor"}</h3>
      <div className="fin-row">{txt("name", "Nombre comercial", { required: true })}{txt("legal_name", "Razón social")}</div>
      <div className="fin-row">{txt("tax_id", "Tax ID / EIN")}{txt("contact_name", "Persona de contacto")}</div>
      <div className="fin-row">{txt("phone", "Teléfono")}{txt("email", "Correo")}</div>
      {txt("address", "Dirección")}
      <div className="form-field"><span className="form-label">Tipo</span>
        <div className="fin-checks">{Object.entries(cat?.supplier_kinds ?? {}).map(([k, v]) => (
          <label key={k} className="billing-check"><input type="checkbox" checked={(s.kinds ?? []).includes(k)} onChange={() => alternar("kinds", k)} /> {v}</label>))}</div></div>
      <div className="form-field"><span className="form-label">Estados donde opera</span>
        <div className="fin-checks">{["CA", "AZ", "NV"].map((st) => (
          <label key={st} className="billing-check"><input type="checkbox" checked={(s.states ?? []).includes(st)} onChange={() => alternar("states", st)} /> {st}</label>))}</div></div>
      <div className="fin-row">
        <div className="form-field"><label className="form-label" htmlFor="sf-terms">Condiciones de pago (días, 0 = contado)</label>
          <input id="sf-terms" type="number" min={0} max={180} value={s.payment_terms_days ?? 30} onChange={(e) => setS({ ...s, payment_terms_days: Number(e.target.value) })} /></div>
        <div className="form-field"><label className="form-label" htmlFor="sf-method">Forma de pago habitual</label>
          <select id="sf-method" value={s.payment_method ?? ""} onChange={(e) => setS({ ...s, payment_method: e.target.value || null })}>
            <option value="">—</option>{Object.entries(cat?.payment_methods ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></div>
      </div>
      {hasPermission("payables.manage") ? (
        <div className="form-field"><label className="form-label" htmlFor="sf-bank">Datos bancarios (solo los ve Contabilidad)</label>
          <textarea id="sf-bank" rows={2} value={s.bank_details ?? ""} onChange={(e) => setS({ ...s, bank_details: e.target.value || null })} /></div>
      ) : (
        <p className="fin-note">Datos bancarios: {s.bank_details ? "registrados" : "sin registrar"}. Solo Contabilidad los cambia.</p>
      )}
      <div className="fin-row">{txt("license_number", "Licencia de contratista")}
        <div className="form-field"><label className="form-label" htmlFor="sf-lic">Vence la licencia</label>
          <input id="sf-lic" type="date" value={s.license_expires_on ?? ""} onChange={(e) => setS({ ...s, license_expires_on: e.target.value || null })} /></div></div>
      <div className="fin-row">
        <div className="form-field"><label className="form-label" htmlFor="sf-ins">Vence el seguro</label>
          <input id="sf-ins" type="date" value={s.insurance_expires_on ?? ""} onChange={(e) => setS({ ...s, insurance_expires_on: e.target.value || null })} /></div>
        <label className="billing-check fin-center"><input type="checkbox" checked={!!s.w9_on_file} onChange={(e) => setS({ ...s, w9_on_file: e.target.checked })} /> W-9 recibido</label></div>
      <div className="form-field"><label className="form-label" htmlFor="sf-notes">Notas</label>
        <textarea id="sf-notes" rows={2} value={s.notes ?? ""} onChange={(e) => setS({ ...s, notes: e.target.value || null })} /></div>
      <label className="billing-check"><input type="checkbox" checked={s.active ?? true} onChange={(e) => setS({ ...s, active: e.target.checked })} /> Activo</label>
      {initial.id && (
        <div className="fin-box fin-docs">
          <strong>Documentos</strong>
          {(detalle?.documents ?? []).length === 0 ? <p className="acta-empty">Sin documentos.</p> : (
            <ul>{detalle!.documents!.map((d) => (
              <li key={d.id}><button type="button" className="acta-link" onClick={() => openFile(`/payables/supplier-documents/${d.id}/file`)}>{d.kind_label}</button>
                {d.expires_on && ` · vence ${fecha(d.expires_on)}`} <small>{d.filename}</small></li>))}</ul>
          )}
          <div className="fin-inline">
            <select aria-label="Tipo de documento" value={doc.kind} onChange={(e) => setDoc({ ...doc, kind: e.target.value })}>
              {Object.entries(cat?.document_kinds ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <input aria-label="Vence" type="date" value={doc.expires} onChange={(e) => setDoc({ ...doc, expires: e.target.value })} />
            <input aria-label="Archivo" type="file" accept="image/*,application/pdf" onChange={(e) => setDoc({ ...doc, file: e.target.files?.[0] ?? null })} />
            <button type="button" className="acta-btn is-quiet" disabled={!doc.file || subir.isPending} onClick={() => subir.mutate()}>Subir</button>
          </div>
        </div>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending || !s.name?.trim()}>Guardar</button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cancelar</button>
      </div>
    </form>
  );
}

function ImportSuppliers({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [texto, setTexto] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cargar = useMutation({ mutationFn: () => importSuppliers(texto),
    onSuccess: (r) => { setError(null); setMsg(`${r.created} creados, ${r.skipped} ya existían.${r.invalid.length ? ` Sin nombre: ${r.invalid.join(", ")}` : ""}`); qc.invalidateQueries({ queryKey: ["suppliers"] }); },
    onError: (e) => setError(apiErrorMessage(e)) });
  return (
    <div className="fin-box fin-form">
      <p className="acta-lead">Sube el CSV exportado de QuickBooks o Excel. Columnas: nombre, razón social, EIN, contacto, teléfono, correo, dirección, condiciones (días), tipo. Los que ya existen se omiten.</p>
      <input type="file" accept=".csv,text/csv" aria-label="Archivo CSV" onChange={async (e) => { const f = e.target.files?.[0]; if (f) setTexto(await f.text()); }} />
      <textarea rows={4} aria-label="Contenido CSV" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={"Nombre,EIN,Teléfono,Condiciones\nFerguson HVAC,12-3456789,(602) 555-0100,30"} />
      {error && <p className="form-error" role="alert">{error}</p>}
      {msg && <p className="info-banner" role="status">{msg}</p>}
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={!texto.trim() || cargar.isPending} onClick={() => cargar.mutate()}>Importar</button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cerrar</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Antigüedad y ajustes
// ---------------------------------------------------------------------------

function AgingView() {
  const { data } = useQuery({ queryKey: ["payables-aging"], queryFn: payablesAging });
  if (!data) return <p className="acta-empty">Cargando…</p>;
  return (
    <article className="acta">
      <div className="fin-kpis">
        {data.buckets.map((b) => <div key={b.key} className={`fin-kpi${b.key !== "current" && Number(data.totals[b.key]) > 0 ? " is-alert" : ""}`}>
          <small>{b.label}</small><strong>{money(data.totals[b.key])}</strong></div>)}
        <div className="fin-kpi is-total"><small>Total por pagar</small><strong>{money(data.totals.total)}</strong></div>
      </div>
      {data.rows.length === 0 ? <p className="acta-empty">No se le debe nada a ningún proveedor.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Proveedor</th>{data.buckets.map((b) => <th key={b.key}>{b.label}</th>)}<th>Total</th></tr></thead>
          <tbody>{data.rows.map((r) => (
            <tr key={r.supplier_id}><td><strong>{r.supplier_name}</strong><small>{r.invoices} facturas</small></td>
              {data.buckets.map((b) => <td key={b.key} className="mono">{Number(r[b.key]) ? money(r[b.key] as string) : "—"}</td>)}
              <td className="mono"><strong>{money(r.total)}</strong></td></tr>
          ))}</tbody>
        </table></div>
      )}
      <p className="notices-hint">Al {fecha(data.as_of)}. Vencido = días desde la fecha de vencimiento.</p>
    </article>
  );
}

function SettingsView() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["finance-settings"], queryFn: getFinanceSettings });
  const [s, setS] = useState<FinanceSettings | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (data) setS(data); }, [data]);
  const guardar = useMutation({ mutationFn: () => putFinanceSettings(s!), onSuccess: (r) => { qc.setQueryData(["finance-settings"], r); setError(null); setMsg(null); },
    onError: (e) => { setMsg(null); setError(apiErrorMessage(e)); }, meta: { successMessage: "Ajustes guardados." } });
  if (!s) return <p className="acta-empty">Cargando…</p>;
  return (
    <article className="acta">
      <form className="fin-form fin-narrow" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
        <div className="form-field"><label className="form-label" htmlFor="fs-th">Desde este total (USD) la factura necesita dos aprobaciones: Contabilidad y quien autoriza pagos</label>
          <input id="fs-th" inputMode="decimal" value={s.two_approval_threshold} onChange={(e) => setS({ ...s, two_approval_threshold: e.target.value })} /></div>
        <div className="form-field"><label className="form-label" htmlFor="fs-due">Avisar facturas que vencen en estos días</label>
          <input id="fs-due" type="number" min={1} max={60} value={s.due_alert_days} onChange={(e) => setS({ ...s, due_alert_days: Number(e.target.value) })} /></div>
        <div className="form-field"><label className="form-label" htmlFor="fs-doc">Avisar licencias y seguros de proveedores que vencen en estos días</label>
          <input id="fs-doc" type="number" min={1} max={120} value={s.document_alert_days} onChange={(e) => setS({ ...s, document_alert_days: Number(e.target.value) })} /></div>
        <div className="form-field"><label className="form-label" htmlFor="fs-max">Monto máximo de un gasto de campo (USD)</label>
          <input id="fs-max" inputMode="decimal" value={s.max_expense_amount} onChange={(e) => setS({ ...s, max_expense_amount: e.target.value })} /></div>
        {error && <p className="form-error" role="alert">{error}</p>}
        {msg && <p className="info-banner" role="status">{msg}</p>}
        <div className="acta-actions"><button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>Guardar</button></div>
      </form>
    </article>
  );
}
