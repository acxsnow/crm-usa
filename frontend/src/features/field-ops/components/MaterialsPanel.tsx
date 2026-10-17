import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  addMaterial,
  apiErrorMessage,
  deleteMaterial,
  fieldKeys,
  listMaterials,
  useRefreshProject,
} from "@/features/field-ops/module5Api";

/** Unidades de uso común; se puede escribir otra. */
const UNIDADES = ["unidades", "pies (ft)", "metros", "rollos", "cajas", "galones", "libras", "juegos"];

/** «1.00» → «1», «2.50» → «2,5». */
function cantidadLegible(valor: number | string): string {
  return Number(valor).toLocaleString("es-CO", { maximumFractionDigits: 2 });
}

/**
 * Lo que la orden necesita (PDF §5.1, spec D5.8). Lo arma Administración; el
 * técnico lo ve en su orden. No es inventario ni costo: el costo entra a la
 * rentabilidad por las facturas de proveedor y los gastos de campo.
 *
 * Antes era una lista con cantidad, unidad y descripción pegadas y un
 * formulario sin títulos (revisión manual del 16 de octubre).
 */
export function MaterialsPanel({ projectId, canManage, closed }: { projectId: string; canManage: boolean; closed: boolean }) {
  const { data: materiales } = useQuery({ queryKey: fieldKeys.materials(projectId), queryFn: () => listMaterials(projectId) });
  const refresh = useRefreshProject(projectId);
  const [descripcion, setDescripcion] = useState("");
  const [referencia, setReferencia] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [unidad, setUnidad] = useState("unidades");
  const [error, setError] = useState<string | null>(null);
  const editable = canManage && !closed;
  const lista = materiales ?? [];

  const add = useMutation({
    mutationFn: () => addMaterial(projectId, {
      description: descripcion.trim(), quantity: Number(cantidad), unit: unidad.trim() || null,
      sku: referencia.trim() || null, notes: null,
    }),
    onSuccess: () => {
      setError(null);
      setDescripcion("");
      setReferencia("");
      setCantidad("1");
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });
  const remove = useMutation({ mutationFn: deleteMaterial, onSuccess: refresh, onError: (err) => setError(apiErrorMessage(err)) });

  if (!editable && lista.length === 0) return null;
  return (
    <div className="acta-body materials">
      <p className="materials-help">
        Lo que el técnico debe llevar a la instalación. {editable ? "Él lo ve en su orden." : "Lo armó Administración."}
      </p>
      {error && <p className="form-error" role="alert">{error}</p>}

      {lista.length > 0 ? (
        <table className="materials-table">
          <thead>
            <tr>
              <th scope="col">Material</th>
              <th scope="col" className="is-num">Cantidad</th>
              {editable && <th scope="col"><span className="sr-only">Acciones</span></th>}
            </tr>
          </thead>
          <tbody>
            {lista.map((m) => (
              <tr key={m.id}>
                <td>
                  <strong>{m.description}</strong>
                  {m.sku && <small>Ref. {m.sku}</small>}
                </td>
                <td className="is-num">{cantidadLegible(m.quantity)} {m.unit ?? ""}</td>
                {editable && (
                  <td className="is-action">
                    <button type="button" className="acta-btn is-quiet" disabled={remove.isPending}
                      aria-label={`Quitar ${m.description}`} onClick={() => remove.mutate(m.id)}>Quitar</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="acta-empty">Todavía no hay materiales en esta orden.</p>
      )}

      {editable && (
        <form className="materials-form" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          <h5>Agregar material</h5>
          <div className="materials-fields">
            <div className="field is-wide">
              <label htmlFor="mat-desc">Material</label>
              <input id="mat-desc" placeholder="Ej.: línea de refrigerante 3/8 × 3/4" required maxLength={255}
                value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="mat-ref">Referencia <span className="optional">(opcional)</span></label>
              <input id="mat-ref" placeholder="Código o SKU" maxLength={100}
                value={referencia} onChange={(e) => setReferencia(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="mat-qty">Cantidad</label>
              <input id="mat-qty" type="number" inputMode="decimal" min={0.01} step={0.01} required
                value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="mat-unit">Unidad</label>
              <input id="mat-unit" list="mat-units" maxLength={30} placeholder="unidades" pattern="[^0-9].*"
                title="Escribe la unidad con letras, por ejemplo «unidades» o «ft»"
                value={unidad} onChange={(e) => setUnidad(e.target.value)} />
              <datalist id="mat-units">{UNIDADES.map((u) => <option key={u} value={u} />)}</datalist>
            </div>
          </div>
          <button type="submit" className="acta-btn is-primary" disabled={add.isPending}>
            {add.isPending ? "Agregando…" : "Agregar material"}
          </button>
        </form>
      )}
    </div>
  );
}
