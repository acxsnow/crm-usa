import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import "./receipts.css";
import { PaginatedTable, RowAction, RowActions } from "@/components/DataTable";
import { SearchPicker } from "@/components/SearchPicker";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { money } from "@/features/finance/api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { warehouseKeys, type WarehouseItem } from "./api";
import { ItemPicker } from "./ItemPicker";
import {
  closeReceipt,
  createReceipt,
  getReceipt,
  linkReceiptInvoice,
  listActiveLocations,
  receiptInvoiceCandidates,
  receiptKeys,
  receiveReceipt,
  searchReceiptSuppliers,
  setReceiptSupplier,
  SUPPLIERS_PER_SEARCH,
  type Receipt,
  type SupplierOption,
} from "./receiptsApi";

const PAGE_SIZE = 25;
const FACTURAS_POR_PAGINA = 20;

type Tab = "pendientes" | "sin_factura" | "todas";

/** Cantidades: sin los ceros de sobra («8.00» → «8»). */
const cant = (v: string | null | undefined) => (v == null ? "—" : String(Number(v)));

const num = (v: string) => {
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : NaN;
};

/**
 * Recepción de compras (respuesta 3 del cuestionario: la recibe el supervisor).
 *
 * El supervisor anota lo que se pidió y lo que llegó. Si llegaron 8 de 10, la
 * recepción queda «pendiente por llegar» con los 2 que faltan, y se completa
 * cuando lleguen o se cierra con el faltante. Contabilidad asocia después la
 * factura del proveedor desde aquí, sin volver a digitar los artículos.
 */
export function WarehouseReceiptsPage() {
  const { hasPermission } = useAuth();
  const puedeRecibir = hasPermission("warehouse.manage");
  const puedeFacturar = hasPermission("warehouse.manage") || hasPermission("payables.manage");
  const [tab, setTab] = useState<Tab>("pendientes");
  const [nueva, setNueva] = useState(false);
  const [abierta, setAbierta] = useState<string | null>(null);

  const lista = usePaginatedQuery<Receipt>({
    key: receiptKeys.all, path: "/warehouse/receipts", pageSize: PAGE_SIZE,
    params: { status: tab === "todas" ? undefined : tab },
  });

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Recepción de compras</h1>
          <p>Lo que llega del proveedor entra aquí a la bodega (o a una camioneta). Si llega una parte, el resto queda pendiente hasta que llegue o se cierre.</p>
        </div>
        {puedeRecibir && (
          <div className="acta-actions">
            <button type="button" className="acta-btn is-primary" onClick={() => { setNueva((v) => !v); setAbierta(null); }}>
              {nueva ? "Cerrar" : "Nueva recepción"}
            </button>
          </div>
        )}
      </header>

      {nueva && <ReceiptForm onDone={(r) => { setNueva(false); setAbierta(r.id); setTab(r.status === "abierta" ? "pendientes" : "todas"); }}
        onCancel={() => setNueva(false)} />}

      {abierta && <ReceiptDetail id={abierta} puedeRecibir={puedeRecibir} puedeFacturar={puedeFacturar}
        onClose={() => setAbierta(null)} />}

      <nav className="billing-tabs" role="tablist" aria-label="Recepciones">
        {([["pendientes", "Pendientes por llegar"], ["sin_factura", "Sin factura asociada"], ["todas", "Todas"]] as const).map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k}
            className={`billing-tab${tab === k ? " is-active" : ""}`} onClick={() => setTab(k)}>{l}</button>
        ))}
      </nav>

      <article className="acta">
        <PaginatedTable list={lista} getRowKey={(r) => r.id}
          emptyMessage={tab === "pendientes" ? "No hay compras pendientes por llegar." : "No hay recepciones con este filtro."}
          rowClassName={(r) => (r.status === "abierta" ? "fin-overdue" : undefined)}
          columns={[
            { key: "numero", header: "Recepción", render: (r) => (
              <><strong>{r.number}</strong><small>{r.created_at?.slice(0, 10)}{r.created_by_name ? ` · ${r.created_by_name}` : ""}</small></>
            ) },
            { key: "proveedor", header: "Proveedor", render: (r) => (
              <>{r.supplier_name ?? "—"}{r.document_number && <small>Doc. {r.document_number}</small>}</>
            ) },
            { key: "estado", header: "Estado", render: (r) => (
              <>
                <span className={`billing-chip ${r.status === "abierta" ? "is-partial" : r.status === "recibida" ? "is-paid" : "is-void"}`}>
                  {r.status_label}
                </span>
                {r.status === "abierta" && <small>{r.pending_lines} artículo{r.pending_lines === 1 ? "" : "s"} con pendiente</small>}
              </>
            ) },
            { key: "valor", header: "Recibido", className: "mono", render: (r) => (r.received_value ? money(r.received_value) : "—") },
            { key: "factura", header: "Factura", render: (r) => r.supplier_invoice_number ?? <small>Sin asociar</small> },
            { key: "acciones", header: "", render: (r) => (
              <RowActions>
                <RowAction variant={r.status === "abierta" && puedeRecibir ? "primary" : "link"}
                  onClick={() => { setAbierta(r.id); setNueva(false); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                  {r.status === "abierta" && puedeRecibir ? "Recibir" : "Ver"}
                </RowAction>
              </RowActions>
            ) },
          ]} />
      </article>
    </div>
  );
}

interface LineaForm { key: number; item: WarehouseItem | null; pedido: string; costo: string; llego: string; seriales: string }

let siguiente = 1;
const lineaVacia = (): LineaForm => ({ key: siguiente++, item: null, pedido: "", costo: "", llego: "", seriales: "" });

function useLocations() {
  return useQuery({ queryKey: receiptKeys.locations, queryFn: listActiveLocations, staleTime: 60_000 });
}

function SupplierPicker({ value, onChange, label }: { value: SupplierOption | null; onChange: (s: SupplierOption | null) => void; label: string }) {
  return (
    <>
    <span className="form-label" aria-hidden="true">{label}</span>
    <SearchPicker<SupplierOption>
      label={label}
      value={value}
      onChange={onChange}
      search={searchReceiptSuppliers}
      queryKey={receiptKeys.suppliers}
      getKey={(s) => s.id}
      getLabel={(s) => s.name}
      pageSize={SUPPLIERS_PER_SEARCH}
      placeholder="Busca el proveedor"
      clearLabel="Sin proveedor"
    />
    </>
  );
}

/** La compra que llega: proveedor, documento y los artículos con lo pedido y lo que llegó. */
function ReceiptForm({ onDone, onCancel }: { onDone: (r: Receipt) => void; onCancel: () => void }) {
  const qc = useQueryClient();
  const { data: lugares = [] } = useLocations();
  const [proveedor, setProveedor] = useState<SupplierOption | null>(null);
  const [nombreLibre, setNombreLibre] = useState("");
  const [documento, setDocumento] = useState("");
  const [fechaDoc, setFechaDoc] = useState("");
  const [lugar, setLugar] = useState("");
  const [impuesto, setImpuesto] = useState("");
  const [envio, setEnvio] = useState("");
  const [nota, setNota] = useState("");
  const [lineas, setLineas] = useState<LineaForm[]>([lineaVacia()]);
  const [error, setError] = useState<string | null>(null);

  const cambiar = (key: number, cambios: Partial<LineaForm>) =>
    setLineas((ls) => ls.map((l) => (l.key === key ? { ...l, ...cambios } : l)));

  const subtotal = useMemo(() => lineas.reduce((s, l) => s + (num(l.pedido) || 0) * (num(l.costo) || 0), 0), [lineas]);
  const total = subtotal + (num(impuesto) || 0) + (num(envio) || 0);

  const guardar = useMutation({
    mutationFn: () => {
      const usadas = lineas.filter((l) => l.item);
      if (!proveedor && !nombreLibre.trim()) throw new Error("Indica el proveedor.");
      if (usadas.length === 0) throw new Error("Agrega al menos un artículo.");
      for (const l of usadas) {
        if (!(num(l.pedido) > 0)) throw new Error(`Escribe cuánto se pidió de «${l.item?.name}».`);
        if (l.llego !== "" && (num(l.llego) < 0 || num(l.llego) > num(l.pedido)))
          throw new Error(`De «${l.item?.name}» no pueden llegar más de los que se pidieron.`);
        if (l.costo !== "" && !(num(l.costo) >= 0)) throw new Error(`El costo de «${l.item?.name}» no es válido.`);
      }
      return createReceipt({
        supplier_id: proveedor?.id ?? null,
        supplier_name: proveedor ? null : nombreLibre.trim(),
        document_number: documento.trim() || null,
        document_date: fechaDoc || null,
        location_id: lugar || null,
        tax: impuesto || null,
        shipping: envio || null,
        note: nota.trim() || null,
        lines: usadas.map((l) => ({
          item_id: l.item!.id,
          ordered_quantity: l.pedido,
          unit_cost: l.costo || "0",
          received: l.llego === "" ? null : l.llego,
          serials: l.item!.has_serial ? l.seriales.split(/\n|,/).map((s) => s.trim()).filter(Boolean) : null,
        })),
      });
    },
    onSuccess: (r) => {
      setError(null);
      [receiptKeys.all, warehouseKeys.stock, warehouseKeys.items, warehouseKeys.movements, warehouseKeys.summary].forEach((k) =>
        qc.invalidateQueries({ queryKey: k }));
      // El detalle se abre con lo que devolvió el guardado, sin esperar otra consulta.
      qc.setQueryData(receiptKeys.one(r.id), r);
      onDone(r);
    },
    onError: (e) => setError(e instanceof Error && !("response" in e) ? e.message : apiErrorMessage(e)),
  });

  return (
    <article className="acta fin-form fin-box">
      <h3 className="acta-section-title">Nueva recepción</h3>
      <p className="acta-lead">Escribe lo que dice la factura o la remisión. En «Llegó» va lo que se recibe hoy: si llegó todo, deja la misma cantidad; si no llegó nada todavía, déjalo vacío.</p>
      <div className="fin-row">
        <div className="form-field">
          <SupplierPicker label="Proveedor registrado" value={proveedor} onChange={setProveedor} />
        </div>
        {!proveedor && (
          <div className="form-field">
            <label className="form-label" htmlFor="rec-prov-libre">…o nombre del proveedor (si no está registrado)</label>
            <input id="rec-prov-libre" value={nombreLibre} maxLength={255} onChange={(e) => setNombreLibre(e.target.value)} placeholder="Ej. Home Depot" />
          </div>
        )}
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="rec-doc">Número de factura o remisión</label>
          <input id="rec-doc" value={documento} maxLength={80} onChange={(e) => setDocumento(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="rec-fecha">Fecha del documento</label>
          <input id="rec-fecha" type="date" value={fechaDoc} onChange={(e) => setFechaDoc(e.target.value)} />
        </div>
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="rec-lugar">Dónde se recibe</label>
          <select id="rec-lugar" value={lugar} onChange={(e) => setLugar(e.target.value)}>
            <option value="">Bodega</option>
            {lugares.filter((l) => l.kind !== "warehouse").map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </div>
        <div className="form-field rec-money-pair">
          <div>
            <label className="form-label" htmlFor="rec-tax">Impuesto</label>
            <input id="rec-tax" inputMode="decimal" value={impuesto} onChange={(e) => setImpuesto(e.target.value)} placeholder="0.00" />
          </div>
          <div>
            <label className="form-label" htmlFor="rec-ship">Envío</label>
            <input id="rec-ship" inputMode="decimal" value={envio} onChange={(e) => setEnvio(e.target.value)} placeholder="0.00" />
          </div>
        </div>
      </div>

      <div className="rec-lines" role="group" aria-label="Artículos de la compra">
        {lineas.map((l, i) => (
          <div className="rec-line" key={l.key}>
            <div className="rec-line-item">
              <span className="form-label" aria-hidden="true">Artículo {i + 1}</span>
              <ItemPicker itemId={l.item?.id ?? ""} label={`Artículo ${i + 1}`}
                onChange={(item) => cambiar(l.key, { item, costo: l.costo || (item ? String(Number(item.unit_cost)) : "") })} />
            </div>
            <div className="rec-line-nums">
              <div>
                <label className="form-label" htmlFor={`rec-ped-${l.key}`}>Pedido</label>
                <input id={`rec-ped-${l.key}`} inputMode="decimal" value={l.pedido}
                  onChange={(e) => cambiar(l.key, { pedido: e.target.value, llego: l.llego === l.pedido ? e.target.value : l.llego })} />
              </div>
              <div>
                <label className="form-label" htmlFor={`rec-lle-${l.key}`}>Llegó</label>
                <input id={`rec-lle-${l.key}`} inputMode="decimal" value={l.llego} onChange={(e) => cambiar(l.key, { llego: e.target.value })} />
              </div>
              <div>
                <label className="form-label" htmlFor={`rec-cos-${l.key}`}>Costo unitario</label>
                <input id={`rec-cos-${l.key}`} inputMode="decimal" value={l.costo} onChange={(e) => cambiar(l.key, { costo: e.target.value })} />
              </div>
            </div>
            {l.item?.has_serial && num(l.llego) > 0 && (
              <div className="form-field">
                <label className="form-label" htmlFor={`rec-ser-${l.key}`}>Seriales de lo que llegó (uno por línea, opcional)</label>
                <textarea id={`rec-ser-${l.key}`} rows={2} value={l.seriales} onChange={(e) => cambiar(l.key, { seriales: e.target.value })} />
              </div>
            )}
            {lineas.length > 1 && (
              <button type="button" className="acta-link is-danger" onClick={() => setLineas((ls) => ls.filter((x) => x.key !== l.key))}>
                Quitar artículo
              </button>
            )}
          </div>
        ))}
        <button type="button" className="acta-btn is-quiet" onClick={() => setLineas((ls) => [...ls, lineaVacia()])}>+ Agregar artículo</button>
      </div>

      <div className="form-field">
        <label className="form-label" htmlFor="rec-nota">Nota (opcional)</label>
        <input id="rec-nota" value={nota} maxLength={2000} onChange={(e) => setNota(e.target.value)} />
      </div>
      <p className="rec-total">Subtotal {money(subtotal.toFixed(2))} · Total con impuesto y envío <strong>{money(total.toFixed(2))}</strong></p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={guardar.isPending} onClick={() => guardar.mutate()}>
          {guardar.isPending ? "Guardando…" : "Guardar recepción"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onCancel}>Cancelar</button>
      </div>
    </article>
  );
}

/** El detalle: lo que llegó, lo pendiente, registrar otra llegada, cerrar y la factura. */
function ReceiptDetail({ id, puedeRecibir, puedeFacturar, onClose }: {
  id: string; puedeRecibir: boolean; puedeFacturar: boolean; onClose: () => void;
}) {
  const qc = useQueryClient();
  const { data: r, isLoading, isError } = useQuery({ queryKey: receiptKeys.one(id), queryFn: () => getReceipt(id) });
  const [llegada, setLlegada] = useState<Record<string, string>>({});
  const [seriales, setSeriales] = useState<Record<string, string>>({});
  const [cerrar, setCerrar] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const refrescar = (nuevo: Receipt) => {
    qc.setQueryData(receiptKeys.one(id), nuevo);
    [receiptKeys.all, warehouseKeys.stock, warehouseKeys.items, warehouseKeys.movements, warehouseKeys.summary].forEach((k) =>
      qc.invalidateQueries({ queryKey: k }));
  };

  const recibir = useMutation({
    mutationFn: () => {
      const lineas = (r?.lines ?? []).filter((l) => num(llegada[l.id] ?? "") > 0).map((l) => ({
        line_id: l.id, quantity: llegada[l.id],
        serials: l.has_serial ? (seriales[l.id] ?? "").split(/\n|,/).map((s) => s.trim()).filter(Boolean) : null,
      }));
      if (lineas.length === 0) throw new Error("Escribe cuánto llegó de al menos un artículo.");
      return receiveReceipt(id, lineas);
    },
    onSuccess: (nuevo) => {
      setError(null); setLlegada({}); setSeriales({});
      setAviso(nuevo.status === "recibida" ? "Llegó todo: la recepción quedó completa." : "Llegada registrada. Lo que falta sigue pendiente.");
      refrescar(nuevo);
    },
    onError: (e) => { setAviso(null); setError(e instanceof Error && !("response" in e) ? e.message : apiErrorMessage(e)); },
  });

  const cerrarMut = useMutation({
    mutationFn: () => closeReceipt(id, motivo.trim()),
    onSuccess: (nuevo) => { setError(null); setCerrar(false); setAviso(`Recepción ${nuevo.status_label.toLowerCase()}.`); refrescar(nuevo); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  if (isError) return <article className="acta fin-box"><p className="form-error" role="alert">No se pudo abrir la recepción.</p></article>;
  if (isLoading || !r) return <article className="acta fin-box"><p>Cargando recepción…</p></article>;
  const abierta = r.status === "abierta";

  return (
    <article className="acta fin-box rec-detail" aria-label={`Recepción ${r.number}`}>
      <div className="rec-detail-head">
        <div>
          <h3 className="acta-section-title">{r.number} · {r.supplier_name}</h3>
          <p className="acta-lead">
            {r.status_label}{r.document_number ? ` · Documento ${r.document_number}` : ""}{r.document_date ? ` del ${r.document_date}` : ""} · Se recibe en {r.location_name}
          </p>
          {r.close_reason && <p className="acta-lead">Motivo del cierre: {r.close_reason}</p>}
        </div>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cerrar detalle</button>
      </div>

      <ul className="rec-detail-lines">
        {r.lines.map((l) => (
          <li key={l.id}>
            <div className="rec-detail-text">
              <strong>{l.item_name}</strong>
              <small>
                Pedido {cant(l.ordered_quantity)} · llegó {cant(l.received_quantity)}
                {Number(l.pending_quantity) > 0 && <> · <b className="rec-pending">faltan {cant(l.pending_quantity)}</b></>}
                {l.landed_unit_cost && <> · {money(l.landed_unit_cost)} c/u con impuesto y envío</>}
              </small>
            </div>
            {abierta && puedeRecibir && Number(l.pending_quantity) > 0 && (
              <div className="rec-arrive">
                <label className="form-label" htmlFor={`lle-${l.id}`}>Llegó ahora</label>
                <input id={`lle-${l.id}`} inputMode="decimal" placeholder={cant(l.pending_quantity)} value={llegada[l.id] ?? ""}
                  onChange={(e) => setLlegada((v) => ({ ...v, [l.id]: e.target.value }))} />
                <button type="button" className="acta-link" onClick={() => setLlegada((v) => ({ ...v, [l.id]: String(Number(l.pending_quantity)) }))}>
                  Todo lo pendiente
                </button>
                {l.has_serial && num(llegada[l.id] ?? "") > 0 && (
                  <textarea aria-label={`Seriales de ${l.item_name}`} rows={2} placeholder="Seriales, uno por línea (opcional)"
                    value={seriales[l.id] ?? ""} onChange={(e) => setSeriales((v) => ({ ...v, [l.id]: e.target.value }))} />
                )}
              </div>
            )}
          </li>
        ))}
      </ul>

      {r.received_value && (
        <p className="rec-total">Recibido hasta hoy <strong>{money(r.received_value)}</strong> de {money(r.total ?? "0")}
          {Number(r.tax) > 0 || Number(r.shipping) > 0 ? ` (incluye impuesto ${money(r.tax ?? "0")} y envío ${money(r.shipping ?? "0")})` : ""}</p>
      )}

      {error && <p className="form-error" role="alert">{error}</p>}
      {aviso && <div className="info-banner" role="status">{aviso}</div>}

      {abierta && puedeRecibir && (
        <div className="acta-actions">
          <button type="button" className="acta-btn is-primary" disabled={recibir.isPending} onClick={() => recibir.mutate()}>
            {recibir.isPending ? "Registrando…" : "Registrar llegada"}
          </button>
          <button type="button" className="acta-btn is-quiet" onClick={() => setCerrar((v) => !v)}>Cerrar con faltante</button>
        </div>
      )}
      {cerrar && (
        <div className="fin-box">
          <div className="form-field">
            <label className="form-label" htmlFor="rec-motivo">¿Por qué no va a llegar lo que falta?</label>
            <input id="rec-motivo" value={motivo} maxLength={2000} onChange={(e) => setMotivo(e.target.value)}
              placeholder="Ej. El proveedor no tiene más; se pidió a otro" />
          </div>
          <div className="acta-actions">
            <button type="button" className="acta-btn is-primary" disabled={!motivo.trim() || cerrarMut.isPending} onClick={() => cerrarMut.mutate()}>
              Confirmar cierre
            </button>
          </div>
        </div>
      )}

      {puedeFacturar && r.status !== "anulada" && <InvoiceLink receipt={r} onSaved={refrescar} />}
    </article>
  );
}

/** Contabilidad asocia la factura del proveedor a lo que ya entró a bodega. */
function InvoiceLink({ receipt, onSaved }: { receipt: Receipt; onSaved: (r: Receipt) => void }) {
  const [elegida, setElegida] = useState("");
  const [proveedor, setProveedor] = useState<SupplierOption | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Facturas por páginas: «Ver más» trae la siguiente página y la suma a la lista.
  const [paginas, setPaginas] = useState(1);
  const { data: pagina } = useQuery({
    queryKey: [...receiptKeys.candidates(receipt.id), paginas],
    queryFn: async () => {
      const partes = await Promise.all(Array.from({ length: paginas }, (_, i) => receiptInvoiceCandidates(receipt.id, i + 1, FACTURAS_POR_PAGINA)));
      return { items: partes.flatMap((p) => p.items), total: partes[0]?.total ?? 0 };
    },
    enabled: Boolean(receipt.supplier_id),
  });
  const candidatas = pagina?.items ?? [];
  const hayMas = (pagina?.total ?? 0) > candidatas.length;
  const asociar = useMutation({
    mutationFn: (invoiceId: string | null) => linkReceiptInvoice(receipt.id, invoiceId),
    onSuccess: (r) => { setError(null); setElegida(""); onSaved(r); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const ponerProveedor = useMutation({
    mutationFn: () => setReceiptSupplier(receipt.id, proveedor!.id),
    onSuccess: (r) => { setError(null); onSaved(r); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  return (
    <section className="rec-invoice" aria-label="Factura del proveedor">
      <h4>Factura del proveedor</h4>
      {receipt.supplier_invoice_id ? (
        <p>
          Asociada: <strong>{receipt.supplier_invoice_number}</strong>
          {receipt.supplier_invoice_total && <> por {money(receipt.supplier_invoice_total)}</>}.{" "}
          <button type="button" className="acta-link is-danger" onClick={() => asociar.mutate(null)}>Quitar</button>
        </p>
      ) : !receipt.supplier_id ? (
        <>
          <p className="acta-lead">Esta recepción se hizo con el nombre «{receipt.supplier_name}». Para asociar la factura, elige el proveedor registrado.</p>
          <SupplierPicker label="Proveedor registrado" value={proveedor} onChange={setProveedor} />
          <div className="acta-actions">
            <button type="button" className="acta-btn" disabled={!proveedor || ponerProveedor.isPending} onClick={() => ponerProveedor.mutate()}>
              Usar este proveedor
            </button>
          </div>
        </>
      ) : candidatas.length === 0 ? (
        <p className="acta-lead">Todavía no hay facturas de {receipt.supplier_name} en Proveedores. Cuando Contabilidad la registre, se asocia aquí.</p>
      ) : (
        <div className="fin-row">
          <div className="form-field">
            <label className="form-label" htmlFor={`fac-${receipt.id}`}>Factura</label>
            <select id={`fac-${receipt.id}`} value={elegida} onChange={(e) => setElegida(e.target.value)}>
              <option value="">Elige la factura…</option>
              {candidatas.map((f) => <option key={f.id} value={f.id}>{f.number} · {f.invoice_date} · {money(f.total)}</option>)}
            </select>
            {hayMas && (
              <button type="button" className="acta-link" onClick={() => setPaginas((n) => n + 1)}>
                Ver facturas más antiguas ({candidatas.length} de {pagina?.total})
              </button>
            )}
          </div>
          <div className="acta-actions">
            <button type="button" className="acta-btn is-primary" disabled={!elegida || asociar.isPending} onClick={() => asociar.mutate(elegida)}>
              Asociar factura
            </button>
          </div>
        </div>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  );
}
