import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hasAnyPermission } from "@/config/navigation";
import { useAuth } from "@/features/auth/AuthContext";
import {
  addMaterial,
  apiErrorMessage,
  deleteMaterial,
  fieldKeys,
  listMaterials,
  useRefreshProject,
} from "@/features/field-ops/module5Api";
import { approveRelease, listProjectReleases, submitRelease } from "@/features/warehouse/api";

const ESTADO_SALIDA: Record<string, string> = {
  borrador: "Borrador", por_autorizar: "Por autorizar", autorizada: "Autorizada",
  rechazada: "Rechazada", entregada: "Entregada",
};

// Qué le falta a cada salida: el camino es borrador → por autorizar → autorizada → entregada.
const SIGUIENTE: Record<string, string> = {
  borrador: "Falta enviarla a autorizar.",
  por_autorizar: "Espera que la autorice otra persona (no quien la pidió).",
  autorizada: "Autorizada: falta que bodega la entregue.",
  rechazada: "Rechazada: revisa el motivo en Salidas y pide otra.",
  entregada: "Entregada: el técnico marca «Lo llevo» al cargar la camioneta.",
};

/** Unidades de uso común; se puede escribir otra. */
const UNIDADES = ["unidades", "pies (ft)", "metros", "rollos", "cajas", "galones", "libras", "juegos"];

/** «1.00» → «1», «2.50» → «2,5». */
function cantidadLegible(valor: number | string): string {
  return Number(valor).toLocaleString("es-CO", { maximumFractionDigits: 2 });
}

/**
 * Lo que la orden necesita (PDF §5.1, spec D5.8). Lo arma Administración; el
 * técnico lo ve en su orden.
 *
 * Desde bodega (plan bodega-cierre, 24 oct): el material sale de bodega con una
 * orden de salida. Aquí se ven las salidas de esta obra con su estado, se pide
 * una nueva («Pedir material a bodega», a nombre del técnico responsable) y lo
 * que bodega entrega entra solo a la lista. Lo que se escribe a mano es lo que
 * no sale de bodega (lo comprado directo para la obra).
 */
export function MaterialsPanel({ projectId, canManage, closed }: { projectId: string; canManage: boolean; closed: boolean }) {
  const { user } = useAuth();
  const veSalidas = hasAnyPermission(
    ["warehouse.read", "warehouse.manage", "warehouse.request_release", "warehouse.approve_release", "warehouse.deliver"], user);
  const puedePedir = hasAnyPermission(["warehouse.request_release", "warehouse.manage"], user);
  const { data: salidas } = useQuery({
    queryKey: ["warehouse-releases", "obra", projectId],
    queryFn: () => listProjectReleases(projectId),
    enabled: veSalidas,
  });
  const puedeAutorizar = hasAnyPermission(["warehouse.approve_release"], user);
  const puedeEntregar = hasAnyPermission(["warehouse.deliver", "warehouse.manage"], user);
  const puedeGestionar = hasAnyPermission(["warehouse.manage"], user);
  const qc = useQueryClient();
  const avanzar = useMutation({
    mutationFn: ({ id, paso }: { id: string; paso: "enviar" | "autorizar" }) =>
      paso === "enviar" ? submitRelease(id) : approveRelease(id),
    onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: ["warehouse-releases"] }); },
    onError: (err) => setError(apiErrorMessage(err)),
  });
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

  if (!editable && lista.length === 0 && (salidas ?? []).length === 0) return null;
  return (
    <div className="acta-body materials">
      <p className="materials-help">
        Lo que el técnico debe llevar a la instalación. El material de bodega se pide con una salida y, al
        entregarse, aparece solo en la lista.
      </p>
      {error && <p className="form-error" role="alert">{error}</p>}

      {veSalidas && (
        <div className="materials-releases">
          <div className="materials-releases-head">
            <h5>Salidas de bodega de esta obra</h5>
            {puedePedir && !closed && (
              <Link className="acta-btn is-primary" to={`/warehouse/releases?nueva=1&obra=${projectId}`}>
                Pedir material a bodega
              </Link>
            )}
          </div>
          {(salidas ?? []).length === 0 ? (
            <p className="acta-empty">Todavía no se ha pedido material a bodega para esta obra.</p>
          ) : (
            <ul>
              {(salidas ?? []).map((s) => {
                const mia = s.requested_by_user_id === user?.id;
                return (
                  <li key={s.id}>
                    <div className="materials-release-main">
                      <Link to="/warehouse/releases"><strong>{s.number ?? "Salida sin número"}</strong></Link>
                      <span className={`billing-chip release-status is-${s.status}`}>{ESTADO_SALIDA[s.status] ?? s.status}</span>
                      <span className="materials-releases-meta">
                        {s.lines.length} {s.lines.length === 1 ? "renglón" : "renglones"}
                        {s.loading && s.loading.loadable > 0 ? ` · cargado ${s.loading.loaded} de ${s.loading.loadable}` : ""}
                      </span>
                    </div>
                    {/* Qué le falta a la salida y, si te toca a ti, el botón para avanzarla. */}
                    <div className="materials-release-next">
                      <small>{SIGUIENTE[s.status]}</small>
                      {s.status === "borrador" && (mia || puedeGestionar) && (
                        <button type="button" className="acta-btn" disabled={avanzar.isPending}
                          onClick={() => avanzar.mutate({ id: s.id, paso: "enviar" })}>Enviar a autorizar</button>
                      )}
                      {s.status === "por_autorizar" && puedeAutorizar && !mia && (
                        <button type="button" className="acta-btn" disabled={avanzar.isPending}
                          onClick={() => avanzar.mutate({ id: s.id, paso: "autorizar" })}>Autorizar</button>
                      )}
                      {s.status === "autorizada" && puedeEntregar && (
                        <Link className="acta-btn" to="/warehouse/releases">Entregar en Salidas</Link>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

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
                  {/* Lo que entregó la bodega: se ve de qué orden de salida vino. */}
                  {m.warehouse_release_line_id
                    ? m.notes && <small>{m.notes}</small>
                    : <small>No sale de bodega</small>}
                </td>
                <td className="is-num">{cantidadLegible(m.quantity)} {m.unit ?? ""}</td>
                {editable && (
                  <td className="is-action">
                    {/* Lo que entregó bodega no se quita: es el rastro de la salida. */}
                    {!m.warehouse_release_line_id && (
                      <button type="button" className="acta-btn is-quiet" disabled={remove.isPending}
                        aria-label={`Quitar ${m.description}`} onClick={() => remove.mutate(m.id)}>Quitar</button>
                    )}
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
          <h5>Agregar material que no sale de bodega</h5>
          <p className="materials-help">Lo comprado directo para esta obra. Lo de bodega se pide arriba.</p>
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
