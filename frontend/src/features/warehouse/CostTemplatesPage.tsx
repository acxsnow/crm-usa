import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { PaginationControls } from "@/components/PaginationControls";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import {
  deleteCostTemplate,
  saveCostTemplate,
  warehouseKeys,
  type CostTemplate,
  type CostTemplateInput,
  type CostTemplateLine,
} from "./api";

const CATEGORIAS: Record<string, string> = {
  target_profit: "Ganancia objetivo",
  sales_rep: "Representante",
  permit: "Permisos",
  materials: "Materiales",
  equipment: "Equipo",
  consumables: "Consumibles",
  labor: "Mano de obra (propia)",
  contractor: "Subcontratista",
  services: "Servicios",
  other: "Otro",
};
const APLICA: Record<string, string> = { both: "Rebate y particular", rebate: "Rebate", particular: "Particular" };
const LINEA_VACIA: CostTemplateLine = { category: "materials", description: "", mode: "percent", value: "" };

/**
 * Plantillas de costo (spec 2026-10-22): cómo se reparte el precio de un tipo de
 * trabajo. Por porcentaje («Trabajo particular ideal»: 40 / 10 / 30 / 20) o por
 * monto fijo (los pedestales de rebate con sus cifras reales). Arman el
 * estimado de cada trabajo; después se ajusta a mano.
 */
export function CostTemplatesPage() {
  const [editando, setEditando] = useState<CostTemplate | "nueva" | null>(null);
  const lista = usePaginatedQuery<CostTemplate>({
    key: warehouseKeys.costTemplates,
    path: "/warehouse/cost-templates",
    pageSize: 20,
  });

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Plantillas de costo</h1>
          <p>
            Cómo se reparte el precio de cada tipo de trabajo. Al armar el estimado de una obra se elige una
            plantilla y después se ajusta a mano, porque cada trabajo es distinto.
          </p>
        </div>
        {!editando && (
          <button type="button" className="acta-btn is-primary" onClick={() => setEditando("nueva")}>Nueva plantilla</button>
        )}
      </header>

      {editando && (
        <TemplateForm key={editando === "nueva" ? "nueva" : editando.id}
          initial={editando === "nueva" ? null : editando} onClose={() => setEditando(null)} />
      )}

      <article className="acta">
        {lista.isLoading ? <p className="acta-empty">Cargando…</p> : (
          <ul className="fin-cards">
            {lista.items.map((t) => (
              <li key={t.id} className={t.active ? undefined : "fin-inactive"}>
                <div className="fin-card-head">
                  <strong>{t.name}</strong>
                  <button type="button" className="acta-btn" onClick={() => setEditando(t)}>Editar</button>
                </div>
                <small>{APLICA[t.applies_to]}{t.job_type ? ` · ${t.job_type}` : ""}{t.active ? "" : " · inactiva"}</small>
                <small>
                  {t.lines.map((l) => `${CATEGORIAS[l.category] ?? l.category} ${l.mode === "percent" ? `${Number(l.value)}%` : `$${Number(l.value).toLocaleString("en-US")}`}`).join(" · ")}
                </small>
              </li>
            ))}
          </ul>
        )}
        <PaginationControls {...lista.controls} />
      </article>
    </div>
  );
}

function TemplateForm({ initial, onClose }: { initial: CostTemplate | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [datos, setDatos] = useState<CostTemplateInput>({
    name: initial?.name ?? "", job_type: initial?.job_type ?? "", applies_to: initial?.applies_to ?? "both",
    active: initial?.active ?? true, lines: initial?.lines.map((l) => ({ ...l })) ?? [{ ...LINEA_VACIA }],
  });
  const [error, setError] = useState<string | null>(null);

  const porcentaje = datos.lines.filter((l) => l.mode === "percent").reduce((s, l) => s + Number(l.value || 0), 0);
  function cambiar(i: number, parcial: Partial<CostTemplateLine>) {
    setDatos((d) => ({ ...d, lines: d.lines.map((l, j) => (j === i ? { ...l, ...parcial } : l)) }));
  }
  function listo() {
    qc.invalidateQueries({ queryKey: warehouseKeys.costTemplates });
    onClose();
  }

  const guardar = useMutation({
    mutationFn: () => saveCostTemplate(initial?.id ?? null, {
      ...datos, job_type: datos.job_type?.trim() || null,
      lines: datos.lines.filter((l) => l.value !== "").map((l) => ({ ...l, description: l.description.trim() })),
    }),
    onSuccess: listo,
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const borrar = useMutation({
    mutationFn: () => deleteCostTemplate(initial!.id),
    onSuccess: listo,
    onError: (e) => setError(apiErrorMessage(e)),
  });

  return (
    <article className="acta fin-form">
      <h2 className="fin-h2">{initial ? `Editar «${initial.name}»` : "Nueva plantilla"}</h2>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="ct-nombre">Nombre</label>
          <input id="ct-nombre" value={datos.name} maxLength={120} onChange={(e) => setDatos({ ...datos, name: e.target.value })} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="ct-tipo">Tipo de trabajo</label>
          <input id="ct-tipo" value={datos.job_type ?? ""} maxLength={100} placeholder="Pedestal, minisplit…"
            onChange={(e) => setDatos({ ...datos, job_type: e.target.value })} />
        </div>
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="ct-aplica">Aplica a</label>
          <select id="ct-aplica" value={datos.applies_to}
            onChange={(e) => setDatos({ ...datos, applies_to: e.target.value as CostTemplate["applies_to"] })}>
            {Object.entries(APLICA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <label className="fin-checks">
          <input type="checkbox" checked={datos.active} onChange={(e) => setDatos({ ...datos, active: e.target.checked })} /> Activa
        </label>
      </div>

      <div className="fin-lines-edit">
        {datos.lines.map((l, i) => (
          <div key={i} className="fin-line">
            <div className="form-field">
              <label className="form-label" htmlFor={`ct-cat-${i}`}>Concepto</label>
              <select id={`ct-cat-${i}`} value={l.category}
                onChange={(e) => cambiar(i, { category: e.target.value, mode: e.target.value === "target_profit" ? "percent" : l.mode })}>
                {Object.entries(CATEGORIAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label className="form-label" htmlFor={`ct-modo-${i}`}>Cómo</label>
              <select id={`ct-modo-${i}`} value={l.mode} disabled={l.category === "target_profit"}
                onChange={(e) => cambiar(i, { mode: e.target.value as CostTemplateLine["mode"] })}>
                <option value="percent">% del precio</option>
                <option value="amount">Monto fijo</option>
              </select>
            </div>
            <div className="form-field">
              <label className="form-label" htmlFor={`ct-valor-${i}`}>{l.mode === "percent" ? "%" : "USD"}</label>
              <input id={`ct-valor-${i}`} inputMode="decimal" value={l.value} onChange={(e) => cambiar(i, { value: e.target.value })} />
            </div>
            <div className="form-field">
              <label className="form-label" htmlFor={`ct-desc-${i}`}>Detalle</label>
              <input id={`ct-desc-${i}`} value={l.description} maxLength={255} onChange={(e) => cambiar(i, { description: e.target.value })} />
            </div>
            <button type="button" className="acta-btn is-quiet fin-center"
              onClick={() => setDatos((d) => ({ ...d, lines: d.lines.filter((_, j) => j !== i) }))}>Quitar</button>
          </div>
        ))}
      </div>
      <p className={`fin-note${porcentaje > 100 ? " is-bad" : ""}`}>Porcentajes: {porcentaje}% (no pueden pasar de 100%).</p>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet" onClick={() => setDatos((d) => ({ ...d, lines: [...d.lines, { ...LINEA_VACIA }] }))}>
          Agregar renglón
        </button>
      </div>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={!datos.name.trim() || guardar.isPending}
          onClick={() => guardar.mutate()}>{guardar.isPending ? "Guardando…" : "Guardar plantilla"}</button>
        {initial && (
          <button type="button" className="acta-btn is-quiet" disabled={borrar.isPending}
            onClick={() => { if (window.confirm("¿Borrar la plantilla? Deja de salir para armar estimados; los que ya la usaron no cambian.")) borrar.mutate(); }}>
            Borrar
          </button>
        )}
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cerrar</button>
      </div>
    </article>
  );
}
