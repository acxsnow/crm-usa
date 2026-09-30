import { LINE_KIND_LABELS, type InvoiceLine, type LineInput } from "@/types/billing";
import { money } from "./billingApi";

export const emptyLine = (): LineInput => ({ kind: "service", description: "", quantity: 1, unit_price: 0 });

export const toInputs = (lines: InvoiceLine[]): LineInput[] =>
  lines.map((l) => ({ kind: l.kind, description: l.description, quantity: l.quantity, unit_price: l.unit_price }));

/** Total mostrado mientras se edita; el que vale es el que calcula el servidor. */
export const linesTotal = (lines: LineInput[]) =>
  lines.reduce((acc, l) => acc + Math.round(l.quantity * l.unit_price * 100) / 100, 0);

/** Líneas de cotización o de factura en borrador: tipo, descripción, cantidad y precio. */
export function LinesEditor({ lines, onChange }: { lines: LineInput[]; onChange: (l: LineInput[]) => void }) {
  const set = (i: number, patch: Partial<LineInput>) => onChange(lines.map((l, n) => (n === i ? { ...l, ...patch } : l)));
  return (
    <div className="lines-editor">
      <div className="lines-row lines-head" aria-hidden="true">
        <span>Tipo</span><span>Descripción</span><span>Cant.</span><span>Precio</span><span className="billing-amount">Importe</span><span />
      </div>
      {lines.map((l, i) => (
        <div className="lines-row" key={i}>
          <select aria-label="Tipo de línea" value={l.kind} onChange={(e) => set(i, { kind: e.target.value })}>
            {Object.entries(LINE_KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input className="lines-desc" aria-label="Descripción" required value={l.description}
            placeholder="Reparación de ductos" onChange={(e) => set(i, { description: e.target.value })} />
          <input aria-label="Cantidad" type="number" min="0.01" step="0.01" required value={l.quantity}
            onChange={(e) => set(i, { quantity: Number(e.target.value) })} />
          <input aria-label="Precio unitario" type="number" min="0" step="0.01" required value={l.unit_price}
            onChange={(e) => set(i, { unit_price: Number(e.target.value) })} />
          <span className="billing-amount">{money(l.quantity * l.unit_price)}</span>
          <button type="button" className="acta-btn is-quiet" aria-label="Quitar línea" disabled={lines.length === 1}
            onClick={() => onChange(lines.filter((_, n) => n !== i))}>✕</button>
        </div>
      ))}
      <div className="acta-actions" style={{ justifyContent: "space-between" }}>
        <button type="button" className="acta-btn is-line" onClick={() => onChange([...lines, emptyLine()])}>+ Agregar línea</button>
        <div className="lines-total"><span>Total</span><span className="billing-amount">{money(linesTotal(lines))}</span></div>
      </div>
    </div>
  );
}
