import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PaginationControls } from "@/components/PaginationControls";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage, localISODate, useInstallers } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import "@/features/finance/finance.css";
import "./jobcost.css";
import { CONCEPT_COLORS, CostBar, DONUT_COLORS, RevenueDonut } from "./JobCostCharts";
import { ExtraChargeForm } from "./ExtraChargeForm";
import { ProjectBudgetPanel } from "./ProjectBudgetPanel";
import {
  applyTemplateToProject,
  deleteCostEntry,
  deliverExtraCharge,
  getJobCosting,
  getProjectBudget,
  listCostTemplatesPage,
  saveCostEntry,
  warehouseKeys,
  type CostEntry,
  type ExtraCharge,
  type JobCosting,
} from "./api";

const MONEDA = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const dinero = (v: string | null | undefined) => (v === null || v === undefined ? "—" : MONEDA.format(Number(v)));
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toFixed(1)}%`);

const COST_CATEGORIES: Record<string, string> = {
  labor: "Mano de obra (técnico propio)",
  contractor: "Subcontratista",
  sales_rep: "Representante",
  permit: "Permiso",
  consumables: "Consumibles",
  other: "Otro",
};

/**
 * Costo del trabajo (spec 2026-10-22): lo que Aldo miraba en Housecall Pro al
 * cerrar un trabajo, con estimado contra real por concepto. Lo real sale solo
 * de lo que ya registra el sistema; aquí se anota lo que no existía: la mano de
 * obra, el pago del representante y el efectivo que el cliente pagó aparte.
 */
export function JobCostPanel({ projectId }: { projectId: string }) {
  const { hasPermission } = useAuth();
  const qc = useQueryClient();
  const puedeArmar = hasPermission("budgets.manage");
  const [error, setError] = useState<string | null>(null);

  const { data: resumen, isLoading } = useQuery({
    queryKey: warehouseKeys.jobCosting(projectId),
    queryFn: () => getJobCosting(projectId),
  });

  function refrescar() {
    for (const key of [warehouseKeys.jobCosting(projectId), warehouseKeys.projectBudget(projectId),
      warehouseKeys.budgetVsActual(projectId), warehouseKeys.costEntries(projectId),
      warehouseKeys.extraCharges(projectId), warehouseKeys.pendingExtras]) {
      qc.invalidateQueries({ queryKey: key });
    }
  }

  const recibir = useMutation({
    mutationFn: (id: string) => deliverExtraCharge(id),
    onSuccess: () => { setError(null); refrescar(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  return (
    <section className="annex-section jobcost" aria-labelledby="anexo-costo">
      <div className="annex-section-head">
        <h3 id="anexo-costo">Costo del trabajo</h3>
        {resumen && <span className="annex-count">{resumen.kind === "rebate" ? "Rebate" : "Particular"}</span>}
      </div>
      <p className="acta-lead">
        Lo que se esperaba ganar contra lo que de verdad dejó el trabajo. Lo real sale de las salidas de bodega,
        las compras y gastos de la obra y lo que se anota aquí (mano de obra, representante, cobros adicionales).
      </p>
      {error && <p className="form-error" role="alert">{error}</p>}

      {isLoading || !resumen ? <p className="acta-empty">Cargando…</p> : <Resumen r={resumen} />}

      {resumen && resumen.extras_pending.length > 0 && (
        <div className="fin-box">
          <h4 className="acta-section-title">Efectivo por entregar</h4>
          <ul className="fin-cards">
            {resumen.extras_pending.map((c: ExtraCharge) => (
              <li key={c.id}>
                <div className="fin-card-head">
                  <strong>{dinero(c.amount)} · {c.description}</strong>
                  {puedeArmar && (
                    <button type="button" className="acta-btn is-primary" disabled={recibir.isPending}
                      onClick={() => recibir.mutate(c.id)}>Recibido</button>
                  )}
                </div>
                <small>{c.charge_date} · lo cobró {c.received_by_name ?? "—"} · {c.payment_method_label}</small>
              </li>
            ))}
          </ul>
        </div>
      )}

      {puedeArmar && <ArmarEstimado projectId={projectId} onDone={refrescar} onError={setError} />}
      {puedeArmar && <CostosAnotados projectId={projectId} onChange={refrescar} />}
      {puedeArmar && (
        <details className="fin-box">
          <summary>Anotar cobro adicional del cliente</summary>
          <ExtraChargeForm projectId={projectId} onSaved={refrescar} />
        </details>
      )}

      <ProjectBudgetPanel projectId={projectId} embedded />
    </section>
  );
}

function Resumen({ r }: { r: JobCosting }) {
  const ingreso = Number(r.revenue.total);
  // Mientras no hay ingreso real, todo el tablero muestra el estimado (spec §6):
  // mezclar el precio esperado con el costo real daría cifras que no cuadran.
  const costos = Number(r.revenue.is_estimate ? r.costs.estimated_total : r.costs.total);
  const etiquetaEstimado = r.revenue.is_estimate ? " (estimado)" : "";
  const conceptos = Object.entries(r.costs.by_concept);
  const ganancia = r.profit.actual ?? r.profit.estimated;
  return (
    <>
      <div className="fin-kpis">
        <div className={`fin-kpi${r.profit.below_target ? " is-alert" : ""}`}>
          <small>Margen{r.profit.margin_pct === null ? " estimado" : " real"}</small>
          <strong>{pct(r.profit.margin_pct ?? r.profit.estimated_margin_pct)}</strong>
          <small>
            estimado {pct(r.profit.estimated_margin_pct)}
            {r.profit.target_pct !== null ? ` · objetivo ${pct(r.profit.target_pct)}` : ""}
          </small>
        </div>
        <div className="fin-kpi">
          <small>Ingreso{etiquetaEstimado}</small>
          <strong>{dinero(r.revenue.total)}</strong>
          {!r.revenue.is_estimate && (
            <small>
              {r.kind === "rebate" ? `Programa ${dinero(r.revenue.program)}` : `Cliente ${dinero(r.revenue.customer)}`}
              {Number(r.revenue.extras) > 0 ? ` · adicionales ${dinero(r.revenue.extras)}` : ""}
            </small>
          )}
        </div>
        <div className="fin-kpi">
          <small><span className="jobcost-dot" style={{ background: DONUT_COLORS.cost }} /> Costos del trabajo{etiquetaEstimado}</small>
          <strong>{dinero(r.revenue.is_estimate ? r.costs.estimated_total : r.costs.total)}</strong>
          <small>{r.revenue.is_estimate ? `real hasta hoy ${dinero(r.costs.total)}` : `estimado ${dinero(r.costs.estimated_total)}`}</small>
        </div>
        <div className="fin-kpi">
          <small><span className="jobcost-dot" style={{ background: DONUT_COLORS.profit }} /> Ganancia{r.profit.actual === null ? " estimada" : ""}</small>
          <strong>{dinero(ganancia)}</strong>
          {r.profit.actual !== null && <small>estimada {dinero(r.profit.estimated)}</small>}
        </div>
      </div>

      {r.profit.below_target && (
        <p className="fin-note is-bad" role="status">La ganancia queda por debajo del objetivo de la plantilla.</p>
      )}
      {r.warnings.includes("possible_duplicate") && (
        <p className="fin-note is-bad" role="status">
          Hay un subcontratista o permiso anotado a mano por el mismo monto de una factura de proveedor de esta obra:
          revisa que no se esté contando dos veces.
        </p>
      )}

      <div className="jobcost-charts">
        <div className="jobcost-donut-wrap">
          <RevenueDonut revenue={ingreso} costs={costos} />
          <div>
            <b>Del ingreso</b>
            <p><span className="jobcost-dot" style={{ background: DONUT_COLORS.profit }} /> Ganancia {ingreso > 0 ? pct(((ingreso - costos) / ingreso) * 100) : "—"}</p>
            <p><span className="jobcost-dot" style={{ background: DONUT_COLORS.cost }} /> Costos {ingreso > 0 ? pct((costos / ingreso) * 100) : "—"}</p>
          </div>
        </div>
        <div>
          <b>En qué se fue el costo</b>
          <CostBar parts={conceptos.map(([key, c]) => ({ key, label: c.label, value: Number(c.actual) }))} />
          <p className="jobcost-legend">
            {conceptos.filter(([, c]) => Number(c.actual) > 0).map(([key, c]) => (
              <span key={key}><span className="jobcost-dot" style={{ background: CONCEPT_COLORS[key] }} /> {c.label} {dinero(c.actual)}</span>
            ))}
          </p>
        </div>
      </div>

      <div className="tablewrap">
        <table className="notices-table jobcost-table">
          <thead>
            <tr><th scope="col">Concepto</th><th scope="col">Estimado</th><th scope="col">% del precio</th>
              <th scope="col">Real</th><th scope="col">Diferencia</th><th scope="col">De dónde sale lo real</th></tr>
          </thead>
          <tbody>
            {conceptos.map(([key, c]) => {
              const precio = Number(r.revenue.expected ?? 0);
              const sube = Number(c.deviation) > 0;
              return (
                <tr key={key}>
                  <td data-label="Concepto">{c.label}</td>
                  <td data-label="Estimado">{dinero(c.estimated)}</td>
                  <td data-label="% del precio">{precio > 0 ? pct((Number(c.estimated) / precio) * 100) : "—"}</td>
                  <td data-label="Real" className={sube ? "fin-danger" : undefined}>{dinero(c.actual)}</td>
                  <td data-label="Diferencia" className={sube ? "fin-danger" : undefined}>
                    {Number(c.deviation) === 0 ? "—" : `${sube ? "+" : ""}${dinero(c.deviation)}`}
                  </td>
                  <td data-label="Fuente"><small>{c.source}</small></td>
                </tr>
              );
            })}
            <tr className="jobcost-total">
              <td data-label="Concepto"><strong>Ganancia neta</strong></td>
              <td data-label="Estimado"><strong>{dinero(r.profit.estimated)}</strong></td>
              <td data-label="% del precio">{pct(r.profit.estimated_margin_pct)}</td>
              <td data-label="Real"><strong>{dinero(r.profit.actual)}</strong></td>
              <td data-label="Diferencia">
                {r.profit.actual !== null && r.profit.estimated !== null
                  ? dinero(String(Number(r.profit.actual) - Number(r.profit.estimated))) : "—"}
              </td>
              <td />
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}

/** Elegir una plantilla y un precio para llenar el estimado en borrador. */
function ArmarEstimado({ projectId, onDone, onError }: {
  projectId: string; onDone: () => void; onError: (m: string | null) => void;
}) {
  const [templateId, setTemplateId] = useState("");
  const [precio, setPrecio] = useState("");
  const { data: plantillas } = useQuery({
    queryKey: [...warehouseKeys.costTemplates, "activas"],
    queryFn: () => listCostTemplatesPage(1, 100, { active: true }).then((p) => p.items),
  });
  const { data: presupuesto } = useQuery({
    queryKey: warehouseKeys.projectBudget(projectId),
    queryFn: () => getProjectBudget(projectId),
  });
  const editable = !presupuesto || presupuesto.status === "borrador";

  const aplicar = useMutation({
    mutationFn: () => applyTemplateToProject(projectId, templateId, precio.trim() || null),
    onSuccess: () => { onError(null); setTemplateId(""); onDone(); },
    onError: (e) => onError(apiErrorMessage(e)),
  });

  return (
    <div className="fin-box">
      <h4 className="acta-section-title">Armar el estimado con una plantilla</h4>
      {!editable && (
        <p className="acta-lead">El estimado ya está aprobado: es contra el que se compara lo real.</p>
      )}
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="jc-plantilla">Plantilla</label>
          <select id="jc-plantilla" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
            <option value="">— Elegir plantilla —</option>
            {(plantillas ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="jc-precio">Precio esperado (USD)</label>
          <input id="jc-precio" inputMode="decimal" value={precio} onChange={(e) => setPrecio(e.target.value)}
            placeholder="Vacío: la tarifa del programa o la cotización" />
        </div>
      </div>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={!editable || !templateId || aplicar.isPending}
          onClick={() => {
            const manuales = (presupuesto?.lines ?? []).filter((l) => !l.item_id).length;
            if (manuales > 0 && !window.confirm(
              `La plantilla reemplaza los ${manuales} renglones escritos a mano del estimado (el material del catálogo se queda). ¿Seguir?`,
            )) return;
            aplicar.mutate();
          }}>
          {aplicar.isPending ? "Aplicando…" : "Aplicar plantilla"}
        </button>
      </div>
    </div>
  );
}

/** Mano de obra, subcontratista y representante: lo que en Housecall Pro es «Labor». */
function CostosAnotados({ projectId, onChange }: { projectId: string; onChange: () => void }) {
  const qc = useQueryClient();
  const [categoria, setCategoria] = useState("labor");
  const [monto, setMonto] = useState("");
  const [fecha, setFecha] = useState(localISODate());
  const [personaId, setPersonaId] = useState("");
  const [personaNombre, setPersonaNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { data: tecnicos } = useInstallers(true);
  const lista = usePaginatedQuery<CostEntry>({
    key: warehouseKeys.costEntries(projectId),
    path: `/warehouse/projects/${projectId}/cost-entries`,
    pageSize: 10,
  });

  function listo() {
    setError(null);
    qc.invalidateQueries({ queryKey: warehouseKeys.costEntries(projectId) });
    onChange();
  }

  const guardar = useMutation({
    mutationFn: () => saveCostEntry(projectId, null, {
      entry_date: fecha, category: categoria, amount: monto, description: descripcion.trim() || null,
      person_user_id: personaId || null, person_name: personaId ? null : personaNombre.trim() || null,
    }),
    onSuccess: () => { setMonto(""); setDescripcion(""); listo(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const borrar = useMutation({
    mutationFn: (id: string) => deleteCostEntry(projectId, id),
    onSuccess: listo,
    onError: (e) => setError(apiErrorMessage(e)),
  });

  return (
    <div className="fin-box">
      <h4 className="acta-section-title">Mano de obra y representante</h4>
      <p className="acta-lead">Interno: el cliente nunca lo ve. El pago de Luis puede ir como «Representante» o como mano de obra.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="jc-cat">Concepto</label>
          <select id="jc-cat" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            {Object.entries(COST_CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="jc-monto">Monto (USD)</label>
          <input id="jc-monto" inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} />
        </div>
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="jc-tecnico">Técnico</label>
          <select id="jc-tecnico" value={personaId} onChange={(e) => setPersonaId(e.target.value)}>
            <option value="">— Otra persona o compañía —</option>
            {(tecnicos ?? []).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="jc-nombre">Nombre (si no es un técnico)</label>
          <input id="jc-nombre" value={personaNombre} disabled={!!personaId} maxLength={255}
            onChange={(e) => setPersonaNombre(e.target.value)} placeholder="Luis, HVAC Pros LLC…" />
        </div>
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="jc-fecha">Fecha</label>
          <input id="jc-fecha" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="jc-desc">Detalle</label>
          <input id="jc-desc" value={descripcion} maxLength={255} onChange={(e) => setDescripcion(e.target.value)} />
        </div>
      </div>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={!monto || guardar.isPending}
          onClick={() => guardar.mutate()}>{guardar.isPending ? "Guardando…" : "Anotar"}</button>
      </div>

      {lista.items.length > 0 && (
        <ul className="fin-cards">
          {lista.items.map((e) => (
            <li key={e.id}>
              <div className="fin-card-head">
                <strong>{e.category_label} · {dinero(e.amount)}</strong>
                <button type="button" className="acta-btn is-quiet" disabled={borrar.isPending}
                  onClick={() => { if (window.confirm("¿Borrar este costo?")) borrar.mutate(e.id); }}>Borrar</button>
              </div>
              <small>{e.entry_date} · {e.person_name ?? "—"} · {e.description}</small>
            </li>
          ))}
        </ul>
      )}
      <PaginationControls {...lista.controls} />
    </div>
  );
}
