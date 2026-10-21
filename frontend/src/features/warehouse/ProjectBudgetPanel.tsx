import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import {
  approveBudget,
  applyKitToBudget,
  deleteBudget,
  getBudgetVsActual,
  getProjectBudget,
  listItemsPage,
  listKitsPage,
  saveBudget,
  warehouseCatalogs,
  warehouseKeys,
  type BudgetLineInput,
  type BudgetVsActual,
  type ProjectBudget,
} from "./api";

const MONEDA = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function dinero(valor: string | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return MONEDA.format(Number(valor));
}

function porcentaje(valor: number | null): string {
  return valor === null ? "—" : `${valor.toFixed(1)}%`;
}

const ESTADOS: Record<string, string> = {
  borrador: "Borrador", aprobado: "Aprobado", reemplazado: "Reemplazado",
};

const RENGLON_VACIO: BudgetLineInput = { category: "materials", item_id: "", quantity: "1", unit: "", unit_cost: "", description: "" };

/**
 * El presupuesto de la obra y su comparación contra el costo real (punto 3 del
 * cuestionario del 19 de octubre).
 *
 * «Le gustaría que en cada proyecto se pueda hacer un presupuesto o un estimado
 * y comparar con los gastos reales». El estimado se arma aquí; el real sale de
 * las salidas de bodega valoradas, los gastos aprobados y las compras cargadas
 * directo a la obra, así que solo se muestra.
 */
export function ProjectBudgetPanel({ projectId }: { projectId: string }) {
  const { hasPermission } = useAuth();
  const qc = useQueryClient();
  const puedeArmar = hasPermission("budgets.manage");
  const puedeAprobar = hasPermission("budgets.approve");
  const [editando, setEditando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });
  const { data: presupuesto, isLoading } = useQuery({
    queryKey: warehouseKeys.projectBudget(projectId),
    queryFn: () => getProjectBudget(projectId),
  });
  const { data: comparacion } = useQuery({
    queryKey: warehouseKeys.budgetVsActual(projectId),
    queryFn: () => getBudgetVsActual(projectId),
  });

  function refrescar() {
    qc.invalidateQueries({ queryKey: warehouseKeys.projectBudget(projectId) });
    qc.invalidateQueries({ queryKey: warehouseKeys.budgetVsActual(projectId) });
    qc.invalidateQueries({ queryKey: warehouseKeys.budgets });
    qc.invalidateQueries({ queryKey: warehouseKeys.purchasing });
  }

  const aprobar = useMutation({
    mutationFn: (id: string) => approveBudget(id),
    onSuccess: () => { setError(null); refrescar(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const borrar = useMutation({
    mutationFn: (id: string) => deleteBudget(id),
    onSuccess: () => { setError(null); setEditando(false); refrescar(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  const esBorrador = presupuesto?.status === "borrador";
  const etiqueta = presupuesto ? ESTADOS[presupuesto.status] ?? presupuesto.status : "Sin presupuesto";

  return (
    <section className="annex-section" aria-labelledby="anexo-presupuesto">
      <div className="annex-section-head">
        <h3 id="anexo-presupuesto">Presupuesto</h3>
        <span className="annex-count">{etiqueta}</span>
      </div>
      <p className="acta-lead">
        El estimado de la obra contra lo que de verdad costó. El costo real sale de las salidas de bodega
        valoradas a costo del catálogo, los gastos aprobados y las compras cargadas directo a la obra.
      </p>

      {error && <p className="form-error" role="alert">{error}</p>}

      {isLoading ? (
        <p className="acta-empty">Cargando…</p>
      ) : editando || (esBorrador && puedeArmar) ? (
        <BudgetForm
          key={presupuesto?.id ?? "nuevo"}
          projectId={projectId}
          initial={presupuesto ?? null}
          catalogs={cat}
          onClose={() => setEditando(false)}
          onSaved={refrescar}
        />
      ) : !presupuesto ? (
        <>
          <p className="acta-empty">Esta obra todavía no tiene presupuesto.</p>
          {puedeArmar && (
            <div className="acta-actions">
              <button type="button" className="acta-btn is-primary" onClick={() => setEditando(true)}>Armar presupuesto</button>
            </div>
          )}
        </>
      ) : (
        <>
          <div className="acta-actions">
            {esBorrador && puedeArmar && (
              <button type="button" className="acta-btn" onClick={() => setEditando(true)}>Editar el borrador</button>
            )}
            {esBorrador && puedeAprobar && (
              <button type="button" className="acta-btn is-primary" disabled={aprobar.isPending}
                onClick={() => aprobar.mutate(presupuesto.id)}>
                {aprobar.isPending ? "Aprobando…" : "Aprobar presupuesto"}
              </button>
            )}
            {esBorrador && puedeArmar && (
              <button type="button" className="acta-btn is-quiet" disabled={borrar.isPending}
                onClick={() => { if (window.confirm("¿Borrar el borrador del presupuesto?")) borrar.mutate(presupuesto.id); }}>
                Borrar
              </button>
            )}
          </div>

          <table className="materials-table">
            <thead>
              <tr><th scope="col">Categoría</th><th scope="col">Descripción</th><th scope="col">Cantidad</th>
                <th scope="col">Costo unitario</th><th scope="col">Monto</th></tr>
            </thead>
            <tbody>
              {presupuesto.lines.map((r) => (
                <tr key={r.id}>
                  <td>{cat?.budget_categories?.[r.category] ?? r.category}</td>
                  <td>{r.item_name ?? r.description}{r.notes ? <small>{r.notes}</small> : null}</td>
                  <td>{r.quantity} {r.unit_label ?? ""}</td>
                  <td>{dinero(r.unit_cost)}</td>
                  <td>{dinero(r.amount)}</td>
                </tr>
              ))}
              <tr>
                <td colSpan={4}><strong>Total estimado</strong></td>
                <td><strong>{dinero(presupuesto.total)}</strong></td>
              </tr>
            </tbody>
          </table>
        </>
      )}

      {presupuesto && comparacion && <ComparisonTable comparacion={comparacion} />}
    </section>
  );
}

/** Estimado contra real, por categoría. Se muestra siempre que haya presupuesto. */
function ComparisonTable({ comparacion }: { comparacion: BudgetVsActual }) {
  return (
    <>
      <h4 className="acta-section-title">Estimado contra real</h4>
      <div className="tablewrap"><table className="notices-table">
        <thead>
          <tr><th>Categoría</th><th>Estimado</th><th>Real</th><th>Desviación</th><th>%</th></tr>
        </thead>
        <tbody>
          {comparacion.rows.map((f) => (
            <tr key={f.category}>
              <td>{f.label}</td>
              <td>{dinero(f.estimated)}</td>
              <td>{dinero(f.actual)}</td>
              <td className={Number(f.deviation) > 0 ? "is-negative" : undefined}>{dinero(f.deviation)}</td>
              <td>{porcentaje(f.deviation_pct)}</td>
            </tr>
          ))}
          <tr>
            <td><strong>Total</strong></td>
            <td><strong>{dinero(comparacion.totals.estimated)}</strong></td>
            <td><strong>{dinero(comparacion.totals.actual)}</strong></td>
            <td><strong>{dinero(comparacion.totals.deviation)}</strong></td>
            <td><strong>{porcentaje(comparacion.totals.deviation_pct)}</strong></td>
          </tr>
        </tbody>
      </table></div>
      <p className="acta-lead">
        Una desviación positiva quiere decir que se gastó más de lo presupuestado. Los gastos de campo se
        gastan pero no se presupuestan, así que su estimado sale en cero.
      </p>
    </>
  );
}

/**
 * Armar o editar el borrador: los renglones con categoría, cantidad y costo, y
 * el atajo para cargar de golpe una lista predefinida por tipo de trabajo.
 */
function BudgetForm({ projectId, initial, catalogs, onClose, onSaved }: {
  projectId: string;
  initial: ProjectBudget | null;
  catalogs: { budget_categories?: Record<string, string>; units?: Record<string, string> } | undefined;
  onClose: () => void;
  onSaved: () => void;
}) {
  const qc = useQueryClient();
  const [notas, setNotas] = useState(initial?.notes ?? "");
  const [kitId, setKitId] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [renglones, setRenglones] = useState<BudgetLineInput[]>(
    initial?.lines.length
      ? initial.lines.map((r) => ({
          category: r.category, item_id: r.item_id ?? "", description: r.description,
          quantity: r.quantity, unit: r.unit ?? "", unit_cost: r.unit_cost, notes: r.notes ?? "",
        }))
      : [{ ...RENGLON_VACIO }],
  );

  const { data: articulos } = useQuery({
    queryKey: [...warehouseKeys.items, "para-presupuesto"],
    queryFn: () => listItemsPage(1, 200, { active: true }).then((p) => p.items),
  });
  const { data: listas } = useQuery({
    queryKey: [...warehouseKeys.kits, "para-presupuesto"],
    queryFn: () => listKitsPage(1, 100, { active: true }).then((p) => p.items),
  });

  const categorias = catalogs?.budget_categories ?? {};
  const unidades = catalogs?.units ?? {};

  const guardar = useMutation({
    mutationFn: () => saveBudget(initial?.id ?? null, {
      project_id: projectId,
      notes: notas.trim() || null,
      lines: renglones.map((r) => ({
        category: r.category, item_id: r.item_id || null, description: r.description?.trim() || null,
        quantity: r.quantity, unit: r.unit || null, unit_cost: r.unit_cost || null, notes: r.notes?.trim() || null,
      })),
    }),
    onSuccess: () => { onSaved(); onClose(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  /** Cargar desde una lista: primero el borrador (si aún no existe) y luego la copia. */
  const cargarLista = useMutation({
    mutationFn: async () => {
      let id = initial?.id ?? null;
      if (!id) {
        const creado = await saveBudget(null, {
          project_id: projectId, notes: notas.trim() || null,
          lines: renglones.map((r) => ({ ...r, item_id: r.item_id || null, unit: r.unit || null, unit_cost: r.unit_cost || null })),
        });
        id = creado.id;
      }
      return applyKitToBudget(id, kitId);
    },
    onSuccess: (resultado) => {
      setError(null);
      setAviso(`«${resultado.kit_name}»: ${resultado.agregadas} renglones agregados, ${resultado.omitidas} ya estaban.`);
      setRenglones(resultado.lines.map((r) => ({
        category: r.category, item_id: r.item_id ?? "", description: r.description,
        quantity: r.quantity, unit: r.unit ?? "", unit_cost: r.unit_cost, notes: r.notes ?? "",
      })));
      qc.invalidateQueries({ queryKey: warehouseKeys.projectBudget(projectId) });
      onSaved();
      // El borrador ya existe: se sigue editando sobre sus renglones.
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  function cambiar(i: number, campos: Partial<BudgetLineInput>) {
    setRenglones((actuales) => actuales.map((r, j) => (j === i ? { ...r, ...campos } : r)));
  }

  /** Al elegir un artículo se traen su nombre y su costo del catálogo. */
  function elegirArticulo(i: number, itemId: string) {
    const articulo = (articulos ?? []).find((a) => a.id === itemId);
    cambiar(i, {
      item_id: itemId,
      description: articulo ? articulo.name : "",
      unit: articulo ? articulo.unit : "",
      unit_cost: articulo ? articulo.unit_cost : "",
    });
  }

  const total = renglones.reduce(
    (suma, r) => suma + Number(r.quantity || 0) * Number(r.unit_cost || 0), 0);

  return (
    <div className="fin-form fin-box">
      <h3 className="acta-section-title">{initial ? "Editar el presupuesto" : "Armar el presupuesto"}</h3>
      <p className="acta-lead">
        Cada renglón es una categoría con su cantidad y su costo. Aprobar el presupuesto deja la versión
        anterior como «reemplazada»: la comparación siempre usa la aprobada.
      </p>

      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="pres-lista">Cargar desde una lista predefinida</label>
          <select id="pres-lista" value={kitId} onChange={(e) => setKitId(e.target.value)}>
            <option value="">— Elegir lista —</option>
            {(listas ?? []).map((k) => (
              <option key={k.id} value={k.id}>{k.name}{k.project_type ? ` · ${k.project_type}` : ""}</option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="pres-notas">Notas</label>
          <input id="pres-notas" value={notas} onChange={(e) => setNotas(e.target.value)} maxLength={2000} />
        </div>
      </div>

      {aviso && <p className="acta-lead" role="status">{aviso}</p>}

      <table className="materials-table">
        <thead>
          <tr>
            <th scope="col">Categoría</th><th scope="col">Artículo</th><th scope="col">Descripción</th>
            <th scope="col">Cantidad</th><th scope="col">Unidad</th><th scope="col">Costo unitario</th>
            <th scope="col">Monto</th><th />
          </tr>
        </thead>
        <tbody>
          {renglones.map((r, i) => (
            <tr key={i}>
              <td>
                <select aria-label={`Categoría del renglón ${i + 1}`} value={r.category}
                  onChange={(e) => cambiar(i, { category: e.target.value })}>
                  {Object.entries(categorias).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </td>
              <td>
                <select aria-label={`Artículo del renglón ${i + 1}`} value={r.item_id ?? ""}
                  onChange={(e) => elegirArticulo(i, e.target.value)}>
                  <option value="">— Libre —</option>
                  {(articulos ?? []).map((a) => (
                    <option key={a.id} value={a.id}>{a.name}{a.sku ? ` (${a.sku})` : ""}</option>
                  ))}
                </select>
              </td>
              <td>
                <input aria-label={`Descripción del renglón ${i + 1}`} value={r.description ?? ""}
                  onChange={(e) => cambiar(i, { description: e.target.value })} maxLength={255}
                  placeholder="Cuadrilla, permiso…" />
              </td>
              <td>
                <input aria-label={`Cantidad del renglón ${i + 1}`} inputMode="decimal" value={r.quantity}
                  onChange={(e) => cambiar(i, { quantity: e.target.value })} />
              </td>
              <td>
                <select aria-label={`Unidad del renglón ${i + 1}`} value={r.unit ?? ""}
                  onChange={(e) => cambiar(i, { unit: e.target.value })}>
                  <option value="">—</option>
                  {Object.entries(unidades).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </td>
              <td>
                <input aria-label={`Costo unitario del renglón ${i + 1}`} inputMode="decimal" value={r.unit_cost ?? ""}
                  onChange={(e) => cambiar(i, { unit_cost: e.target.value })} />
              </td>
              <td>{dinero(String((Number(r.quantity || 0) * Number(r.unit_cost || 0)).toFixed(2)))}</td>
              <td>
                {renglones.length > 1 && (
                  <button type="button" className="acta-btn is-quiet"
                    onClick={() => setRenglones((a) => a.filter((_, j) => j !== i))}>Quitar</button>
                )}
              </td>
            </tr>
          ))}
          <tr>
            <td colSpan={6}><strong>Total estimado</strong></td>
            <td><strong>{dinero(total.toFixed(2))}</strong></td>
            <td />
          </tr>
        </tbody>
      </table>

      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet"
          onClick={() => setRenglones((a) => [...a, { ...RENGLON_VACIO }])}>Agregar renglón</button>
        <button type="button" className="acta-btn" disabled={!kitId || cargarLista.isPending}
          onClick={() => cargarLista.mutate()}>
          {cargarLista.isPending ? "Cargando…" : "Cargar la lista"}
        </button>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={guardar.isPending || renglones.length === 0}
          onClick={() => guardar.mutate()}>
          {guardar.isPending ? "Guardando…" : "Guardar el borrador"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cerrar</button>
      </div>
    </div>
  );
}
