import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "./receipts.css";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { warehouseCatalogs, warehouseKeys, type WarehouseItem } from "./api";
import { createMovement, listActiveLocations, receiptKeys } from "./receiptsApi";

const num = (v: string) => {
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : NaN;
};

/**
 * Traslado entre la bodega y una camioneta, o ajuste con motivo (dañado,
 * pérdida, sobrante, entrada sin factura…). Las dos cosas quedan en el libro
 * de movimientos; el saldo nunca se escribe a mano.
 */
export function StockMoveForm({ item, mode, onClose }: { item: WarehouseItem; mode: "traslado" | "ajuste"; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });
  const { data: lugares = [] } = useQuery({ queryKey: receiptKeys.locations, queryFn: listActiveLocations, staleTime: 60_000 });
  const bodega = lugares.find((l) => l.kind === "warehouse")?.id ?? "";
  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState("");
  const [cantidad, setCantidad] = useState("");
  const [sentido, setSentido] = useState<"restar" | "sumar">("restar");
  const [motivo, setMotivo] = useState("");
  const [nota, setNota] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState<string | null>(null);

  const desde = origen || bodega;
  const hay = Number(item.by_location.find((l) => l.location_id === desde)?.quantity ?? 0);

  const guardar = useMutation({
    mutationFn: () => {
      const n = num(cantidad);
      if (!(n > 0)) throw new Error("Escribe una cantidad mayor que cero.");
      if (mode === "traslado") {
        if (!destino || destino === desde) throw new Error("Elige a dónde va el material.");
        if (n > hay) throw new Error(`En el origen solo hay ${hay}.`);
        return createMovement({ item_id: item.id, movement_type: "traslado", quantity: cantidad, location_id: desde,
          to_location_id: destino, note: nota.trim() || null });
      }
      if (!motivo) throw new Error("Elige el motivo del ajuste.");
      if (motivo === "other" && !nota.trim()) throw new Error("Explica el motivo en la nota.");
      return createMovement({ item_id: item.id, movement_type: "ajuste", quantity: sentido === "restar" ? `-${cantidad}` : cantidad,
        location_id: desde, reason: motivo, note: nota.trim() || null });
    },
    onSuccess: () => {
      setError(null);
      setHecho(mode === "traslado" ? "Traslado registrado." : "Ajuste registrado.");
      setCantidad(""); setNota("");
      [warehouseKeys.stock, warehouseKeys.items, warehouseKeys.movements, warehouseKeys.summary].forEach((k) =>
        qc.invalidateQueries({ queryKey: k }));
      qc.invalidateQueries({ queryKey: ["warehouse-count-sheet"] });
    },
    onError: (e) => { setHecho(null); setError(e instanceof Error && !("response" in e) ? e.message : apiErrorMessage(e)); },
  });

  return (
    <article className="acta fin-form fin-box move-form" aria-label={mode === "traslado" ? "Trasladar" : "Ajustar"}>
      <h3 className="acta-section-title">{mode === "traslado" ? "Trasladar" : "Ajustar existencia"}: {item.name}</h3>
      <p className="acta-lead">
        Hay {item.total_quantity} {item.unit_label} en total
        {item.by_location.length > 0 && ` (${item.by_location.map((l) => `${l.name}: ${l.quantity}`).join(", ")})`}.
      </p>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="mv-origen">{mode === "traslado" ? "Desde" : "Dónde"}</label>
          <select id="mv-origen" value={desde} onChange={(e) => setOrigen(e.target.value)}>
            {lugares.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </div>
        {mode === "traslado" ? (
          <div className="form-field">
            <label className="form-label" htmlFor="mv-destino">Hacia</label>
            <select id="mv-destino" value={destino} onChange={(e) => setDestino(e.target.value)}>
              <option value="">Elige…</option>
              {lugares.filter((l) => l.id !== desde).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </div>
        ) : (
          <div className="form-field">
            <label className="form-label" htmlFor="mv-sentido">Qué pasa</label>
            <select id="mv-sentido" value={sentido} onChange={(e) => setSentido(e.target.value as "restar" | "sumar")}>
              <option value="restar">Sale (hay menos)</option>
              <option value="sumar">Entra (hay más)</option>
            </select>
          </div>
        )}
        <div className="form-field">
          <label className="form-label" htmlFor="mv-cant">Cantidad ({item.unit_label})</label>
          <input id="mv-cant" inputMode="decimal" value={cantidad} onChange={(e) => setCantidad(e.target.value)}
            placeholder={mode === "traslado" ? `Hay ${hay}` : ""} />
        </div>
      </div>
      {mode === "ajuste" && (
        <div className="form-field">
          <label className="form-label" htmlFor="mv-motivo">Motivo</label>
          <select id="mv-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)}>
            <option value="">Elige el motivo…</option>
            {Object.entries(cat?.adjustment_reasons ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      )}
      <div className="form-field">
        <label className="form-label" htmlFor="mv-nota">Nota{mode === "ajuste" && motivo === "other" ? "" : " (opcional)"}</label>
        <input id="mv-nota" value={nota} maxLength={2000} onChange={(e) => setNota(e.target.value)} />
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {hecho && <div className="info-banner" role="status">{hecho}</div>}
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={guardar.isPending} onClick={() => guardar.mutate()}>
          {guardar.isPending ? "Guardando…" : mode === "traslado" ? "Trasladar" : "Registrar ajuste"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cerrar</button>
      </div>
    </article>
  );
}
