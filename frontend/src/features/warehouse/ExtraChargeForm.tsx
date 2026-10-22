import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { PaginationControls } from "@/components/PaginationControls";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { createExtraCharge, warehouseKeys, type ExtraCharge } from "./api";

const MONEDA = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const METODOS: Record<string, string> = { cash: "Efectivo", card: "Tarjeta", transfer: "Transferencia", check: "Cheque", other: "Otro" };

/**
 * Cobro adicional al dueño de casa (spec 2026-10-22): un breaker, más cable,
 * mover algo. No va en la factura al programa; casi siempre es efectivo que el
 * técnico recibe en la obra y le entrega a Aldo. Aquí se anota y se ve si ya se
 * entregó. El técnico solo ve los suyos y nunca ve costos ni ganancia.
 */
export function ExtraChargeForm({ projectId, onSaved }: { projectId: string; onSaved?: () => void }) {
  const qc = useQueryClient();
  const [descripcion, setDescripcion] = useState("");
  const [monto, setMonto] = useState("");
  const [metodo, setMetodo] = useState("cash");
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const lista = usePaginatedQuery<ExtraCharge>({
    key: warehouseKeys.extraCharges(projectId),
    path: `/warehouse/projects/${projectId}/extra-charges`,
    pageSize: 10,
  });

  const guardar = useMutation({
    mutationFn: () => createExtraCharge(projectId, { description: descripcion.trim(), amount: monto, payment_method: metodo }),
    onSuccess: (c) => {
      setError(null);
      setAviso(`Anotado: ${MONEDA.format(Number(c.amount))}. Queda por entregar a la oficina.`);
      setDescripcion(""); setMonto("");
      qc.invalidateQueries({ queryKey: warehouseKeys.extraCharges(projectId) });
      onSaved?.();
    },
    onError: (e) => { setAviso(null); setError(apiErrorMessage(e)); },
  });

  return (
    <div className="fin-form">
      {error && <p className="form-error" role="alert">{error}</p>}
      {aviso && <p className="acta-lead" role="status">{aviso}</p>}
      <div className="form-field">
        <label className="form-label" htmlFor={`extra-desc-${projectId}`}>Qué se le cobró al cliente</label>
        <input id={`extra-desc-${projectId}`} value={descripcion} maxLength={255}
          onChange={(e) => setDescripcion(e.target.value)} placeholder="Breaker 30A y 10 ft de cable" />
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor={`extra-monto-${projectId}`}>Monto (USD)</label>
          <input id={`extra-monto-${projectId}`} inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor={`extra-metodo-${projectId}`}>Forma de pago</label>
          <select id={`extra-metodo-${projectId}`} value={metodo} onChange={(e) => setMetodo(e.target.value)}>
            {Object.entries(METODOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </div>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={!descripcion.trim() || !monto || guardar.isPending}
          onClick={() => guardar.mutate()}>{guardar.isPending ? "Guardando…" : "Anotar cobro"}</button>
      </div>
      {lista.items.length > 0 && (
        <ul className="fin-cards">
          {lista.items.map((c) => (
            <li key={c.id}>
              <div className="fin-card-head">
                <strong>{MONEDA.format(Number(c.amount))} · {c.description}</strong>
                <span className={`jobcost-status ${c.status === "recibido" ? "is-ok" : "is-pending"}`}>
                  {c.status === "recibido" ? "Entregado" : "Por entregar"}
                </span>
              </div>
              <small>{c.charge_date} · {c.payment_method_label} · {c.received_by_name ?? "—"}</small>
            </li>
          ))}
        </ul>
      )}
      <PaginationControls {...lista.controls} />
    </div>
  );
}
