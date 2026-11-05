import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { LINE_KIND_LABELS, type InvoiceLine, type LineInput } from "@/types/billing";
import { listItemsPage, listKitsPage, warehouseKeys, type WarehouseItem } from "@/features/warehouse/api";
import { money } from "./billingApi";

export const emptyLine = (): LineInput => ({ kind: "service", description: "", quantity: 1, unit_price: 0 });

export const toInputs = (lines: InvoiceLine[]): LineInput[] =>
  lines.map((l) => {
    const extra = l as { option_key?: string | null; warehouse_item_id?: string | null };
    return { kind: l.kind, description: l.description, quantity: l.quantity, unit_price: l.unit_price,
      option_key: extra.option_key ?? null, warehouse_item_id: extra.warehouse_item_id ?? null };
  });

/** Total mostrado mientras se edita; el que vale es el que calcula el servidor. */
export const linesTotal = (lines: LineInput[]) =>
  lines.reduce((acc, l) => acc + Math.round(l.quantity * l.unit_price * 100) / 100, 0);

/** Los tipos de línea que salen de bodega; la mano de obra no está en bodega. */
const DE_BODEGA = ["material", "equipment"];
/** Material o equipo escrito a mano: no está en bodega y se valida su ingreso aparte. */
const needsWarehouseCheck = (l: LineInput) => DE_BODEGA.includes(l.kind) && !l.warehouse_item_id;

const kindOf = (category: string | null | undefined) => (category === "equipment" ? "equipment" : "material");
const precio = (sale: string | null | undefined) => Number(sale ?? 0) || 0;

/** Líneas de cotización o de factura en borrador: tipo, descripción, cantidad y precio. */
export function LinesEditor({ lines, onChange, options, fromWarehouse = false }: {
  lines: LineInput[];
  onChange: (l: LineInput[]) => void;
  /** Con opciones (básica / premium) cada línea dice a cuál pertenece. */
  options?: { key: string; label: string }[];
  /** Cotización: cargar listas y artículos de bodega (pedido del cliente, 4 nov 2026). */
  fromWarehouse?: boolean;
}) {
  const set = (i: number, patch: Partial<LineInput>) => onChange(lines.map((l, n) => (n === i ? { ...l, ...patch } : l)));
  // Agregar sin dejar la línea vacía del principio.
  const agregar = (nuevas: LineInput[]) =>
    onChange([...lines.filter((l) => l.description.trim() || l.unit_price), ...nuevas]);
  const porValidar = fromWarehouse ? lines.filter((l) => l.description.trim() && needsWarehouseCheck(l)).length : 0;
  return (
    <div className="lines-editor">
      {fromWarehouse && <WarehouseLoader onAdd={agregar} />}
      <div className="lines-row lines-head" aria-hidden="true">
        <span>Tipo</span><span>Descripción</span><span>Cant.</span><span>Precio</span><span className="billing-amount">Importe</span><span />
      </div>
      {lines.map((l, i) => (
        <div className="lines-row" key={i}>
          <select aria-label="Tipo de línea" value={l.kind}
            onChange={(e) => set(i, { kind: e.target.value, ...(DE_BODEGA.includes(e.target.value) ? {} : { warehouse_item_id: null }) })}>
            {Object.entries(LINE_KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input className="lines-desc" aria-label="Descripción" required value={l.description}
            placeholder="Reparación de ductos"
            // Cambiar el texto de un artículo de bodega lo desliga: ya no es ese artículo.
            onChange={(e) => set(i, { description: e.target.value, warehouse_item_id: null })} />
          <input aria-label="Cantidad" type="number" min="0.01" step="0.01" required value={l.quantity}
            onChange={(e) => set(i, { quantity: Number(e.target.value) })} />
          <input aria-label="Precio unitario" type="number" min="0" step="0.01" required value={l.unit_price}
            onChange={(e) => set(i, { unit_price: Number(e.target.value) })} />
          <span className="billing-amount">{money(l.quantity * l.unit_price)}</span>
          <button type="button" className="acta-btn is-quiet" aria-label="Quitar línea" disabled={lines.length === 1}
            onClick={() => onChange(lines.filter((_, n) => n !== i))}>✕</button>
          {fromWarehouse && DE_BODEGA.includes(l.kind) && l.description.trim() && (
            <span className={`lines-origin${l.warehouse_item_id ? " is-ok" : " is-check"}`}>
              {l.warehouse_item_id ? "De bodega" : "No está en bodega · se valida aparte"}
            </span>
          )}
          {!!options?.length && (
            <label className="lines-option">
              <span>Va en</span>
              <select value={l.option_key ?? ""} onChange={(e) => set(i, { option_key: e.target.value || null })}>
                <option value="">Todas las opciones</option>
                {options.map((o) => <option key={o.key} value={o.key}>{o.label || `Opción ${o.key}`}</option>)}
              </select>
            </label>
          )}
        </div>
      ))}
      {porValidar > 0 && (
        <p className="lines-check-note" role="status">
          {porValidar === 1 ? "1 material no está en bodega" : `${porValidar} materiales no están en bodega`}: se cotizan,
          pero su ingreso se valida aparte con Bodega antes de la obra.
        </p>
      )}
      <div className="acta-actions" style={{ justifyContent: "space-between" }}>
        <button type="button" className="acta-btn is-line" onClick={() => onChange([...lines, emptyLine()])}>+ Agregar línea</button>
        {options?.length ? (
          <div className="lines-total">
            {options.map((o) => (
              <span key={o.key}>{o.label || `Opción ${o.key}`}: <span className="billing-amount">
                {money(linesTotal(lines.filter((l) => !l.option_key || l.option_key === o.key)))}</span></span>
            ))}
          </div>
        ) : <div className="lines-total"><span>Total</span><span className="billing-amount">{money(linesTotal(lines))}</span></div>}
      </div>
    </div>
  );
}

/**
 * Cargar a la cotización una lista predefinida de bodega (como en el
 * presupuesto de la obra) o un artículo suelto del catálogo, con su precio de
 * venta. La mano de obra no está en bodega: se agrega como línea aparte.
 */
function WarehouseLoader({ onAdd }: { onAdd: (l: LineInput[]) => void }) {
  const [kitId, setKitId] = useState("");
  const [texto, setTexto] = useState("");
  const [buscado, setBuscado] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  useEffect(() => {
    const t = setTimeout(() => setBuscado(texto.trim()), 300);
    return () => clearTimeout(t);
  }, [texto]);
  const { data: kits } = useQuery({
    queryKey: [...warehouseKeys.kits, "para-cotizacion"],
    queryFn: () => listKitsPage(1, 100, { active: true }).then((p) => p.items),
  });
  const { data: articulos } = useQuery({
    queryKey: [...warehouseKeys.items, "para-cotizacion", buscado],
    queryFn: () => listItemsPage(1, 8, { q: buscado, active: true }).then((p) => p.items),
    enabled: buscado.length >= 2,
  });

  const cargarLista = () => {
    const kit = kits?.find((k) => k.id === kitId);
    if (!kit) return;
    const sinPrecio = kit.items.filter((r) => !precio(r.sale_price)).length;
    onAdd(kit.items.map((r) => ({
      kind: kindOf(r.category), quantity: Number(r.quantity) || 1, unit_price: precio(r.sale_price),
      description: [r.item_name ?? "Artículo", r.spec_label].filter(Boolean).join(" · "), warehouse_item_id: r.item_id,
    })));
    setAviso(`«${kit.name}»: ${kit.items.length} renglones agregados${sinPrecio ? `; ${sinPrecio} sin precio de venta en bodega, escríbelo` : ""}. Agrega la mano de obra aparte.`);
    setKitId("");
  };
  const elegir = (a: WarehouseItem) => {
    onAdd([{ kind: kindOf(a.category), description: a.name, quantity: 1, unit_price: precio(a.sale_price), warehouse_item_id: a.id }]);
    setAviso(precio(a.sale_price) ? null : `«${a.name}» no tiene precio de venta en bodega: escríbelo en la línea.`);
    setTexto("");
  };

  return (
    <div className="lines-loader">
      <div className="field">
        <label htmlFor="cot-lista">Cargar lista de bodega</label>
        <div className="lines-loader-row">
          <select id="cot-lista" value={kitId} onChange={(e) => setKitId(e.target.value)}>
            <option value="">Elige una lista</option>
            {(kits ?? []).map((k) => <option key={k.id} value={k.id}>{k.name} ({k.items.length})</option>)}
          </select>
          <button type="button" className="acta-btn" disabled={!kitId} onClick={cargarLista}>Cargar</button>
        </div>
      </div>
      <div className="field lines-loader-search">
        <label htmlFor="cot-articulo">O un artículo de bodega</label>
        <input id="cot-articulo" type="search" autoComplete="off" value={texto} placeholder="Nombre o código"
          onChange={(e) => setTexto(e.target.value)} />
        {buscado.length >= 2 && (
          <ul className="customer-search-results" role="listbox" aria-label="Artículos de bodega">
            {(articulos ?? []).map((a) => (
              <li key={a.id}>
                <button type="button" role="option" aria-selected={false} onClick={() => elegir(a)}>
                  <strong>{a.name}</strong>
                  <small>{[a.sku, a.sale_price ? money(Number(a.sale_price)) : "sin precio de venta"].filter(Boolean).join(" · ")}</small>
                </button>
              </li>
            ))}
            {articulos?.length === 0 && <li className="customer-search-empty">Nada en bodega con «{buscado}». Agrégalo como línea: queda por validar.</li>}
          </ul>
        )}
      </div>
      {aviso && <p className="lines-check-note" role="status">{aviso}</p>}
    </div>
  );
}
