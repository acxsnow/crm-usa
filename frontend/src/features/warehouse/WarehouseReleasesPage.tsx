import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { PaginationControls } from "@/components/PaginationControls";
import { useAuth } from "@/features/auth/AuthContext";
import { listProjectsPage } from "@/features/field-ops/api";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import {
  approveRelease,
  createRelease,
  deliverRelease,
  listItemsPage,
  listKitsPage,
  rejectRelease,
  submitRelease,
  warehouseCatalogs,
  warehouseKeys,
  type DeliverResult,
  type ReleaseLineInput,
  type WarehouseRelease,
} from "./api";

const PAGE_SIZE = 25;

/** Las claves que cualquier movimiento de bodega deja desactualizadas. */
function invalidarBodega(qc: ReturnType<typeof useQueryClient>) {
  [warehouseKeys.releases, warehouseKeys.pendingReleases, warehouseKeys.stock,
   warehouseKeys.items, warehouseKeys.movements, warehouseKeys.summary].forEach((key) =>
    qc.invalidateQueries({ queryKey: key }));
}

/**
 * Órdenes de salida de bodega (punto 1 del cuestionario del 19 de octubre).
 *
 * El material no sale «a mano»: el técnico arma la orden, un supervisor la
 * autoriza y solo entonces Bodega la entrega y baja el saldo. La bandeja de
 * arriba es el trabajo del supervisor; la lista de abajo, el histórico.
 */
export function WarehouseReleasesPage() {
  const { hasPermission } = useAuth();
  const qc = useQueryClient();
  const puedePedir = hasPermission("warehouse.request_release") || hasPermission("warehouse.manage");
  const puedeAutorizar = hasPermission("warehouse.approve_release");
  const puedeEntregar = hasPermission("warehouse.deliver") || hasPermission("warehouse.manage");

  const [tab, setTab] = useState<"pendientes" | "todas">(puedeAutorizar ? "pendientes" : "todas");
  const [filtros, setFiltros] = useState<Record<string, string>>({});
  const [creando, setCreando] = useState(false);
  const [rechazando, setRechazando] = useState<{ id: string; numero: string } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [entrega, setEntrega] = useState<DeliverResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });

  const pendientes = usePaginatedQuery<WarehouseRelease>({
    key: warehouseKeys.pendingReleases, path: "/warehouse/releases/pending", pageSize: PAGE_SIZE,
    enabled: puedeAutorizar && tab === "pendientes",
  });

  const params = { status: filtros.status || undefined };
  const todas = usePaginatedQuery<WarehouseRelease>({
    key: warehouseKeys.releases, path: "/warehouse/releases", pageSize: PAGE_SIZE,
    params, enabled: tab === "todas",
  });

  const campos: FilterFieldDef[] = [
    {
      key: "status", label: "Estado", type: "select",
      options: Object.entries(cat?.release_statuses ?? {}).map(([value, label]) => ({ value, label })),
    },
  ];

  function alFallar(e: unknown) {
    setError(apiErrorMessage(e));
  }

  const enviar = useMutation({
    mutationFn: submitRelease,
    onSuccess: () => { setError(null); invalidarBodega(qc); },
    onError: alFallar,
  });
  const autorizar = useMutation({
    mutationFn: approveRelease,
    onSuccess: () => { setError(null); invalidarBodega(qc); },
    onError: alFallar,
  });
  const rechazar = useMutation({
    mutationFn: () => rejectRelease(rechazando?.id as string, motivo.trim()),
    onSuccess: () => { setError(null); setRechazando(null); setMotivo(""); invalidarBodega(qc); },
    onError: alFallar,
  });
  const entregar = useMutation({
    mutationFn: (id: string) => deliverRelease(id),
    onSuccess: (r) => { setError(null); setEntrega(r); invalidarBodega(qc); },
    onError: alFallar,
  });

  const lista = tab === "pendientes" ? pendientes : todas;

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Salidas de bodega</h1>
          <p>El material sale solo con una orden autorizada. El técnico la pide, el supervisor la autoriza y Bodega la entrega.</p>
        </div>
        {puedePedir && !creando && (
          <div className="acta-actions">
            <button type="button" className="acta-btn is-primary" onClick={() => setCreando(true)}>Nueva salida</button>
          </div>
        )}
      </header>

      {creando && (
        <ReleaseForm
          onClose={() => setCreando(false)}
          onCreated={() => { setCreando(false); setTab("todas"); invalidarBodega(qc); }}
        />
      )}

      {entrega && <EntregaBanner resultado={entrega} onClose={() => setEntrega(null)} />}

      {rechazando && (
        <form
          className="acta fin-form fin-box"
          onSubmit={(e) => { e.preventDefault(); rechazar.mutate(); }}
        >
          <h3 className="acta-section-title">Rechazar {rechazando.numero}</h3>
          <p className="acta-lead">El técnico recibe el motivo, así que conviene decir qué falta o por qué no se autoriza.</p>
          <div className="form-field">
            <label className="form-label" htmlFor="rel-motivo">Motivo</label>
            <textarea id="rel-motivo" rows={2} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </div>
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={rechazar.isPending || !motivo.trim()}>
              {rechazar.isPending ? "Rechazando…" : "Rechazar la salida"}
            </button>
            <button type="button" className="acta-btn is-quiet" onClick={() => { setRechazando(null); setMotivo(""); }}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {puedeAutorizar && (
        <nav className="billing-tabs" role="tablist" aria-label="Salidas de bodega">
          <button type="button" role="tab" aria-selected={tab === "pendientes"}
            className={`billing-tab${tab === "pendientes" ? " is-active" : ""}`} onClick={() => setTab("pendientes")}>
            Salidas por autorizar
            {pendientes.total > 0 && <span className="billing-count">{pendientes.total}</span>}
          </button>
          <button type="button" role="tab" aria-selected={tab === "todas"}
            className={`billing-tab${tab === "todas" ? " is-active" : ""}`} onClick={() => setTab("todas")}>
            Todas las salidas
          </button>
        </nav>
      )}

      {error && <p className="form-error" role="alert">{error}</p>}

      <article className="acta">
        {tab === "todas" && (
          <FilterBar fields={campos} values={filtros} onApply={setFiltros} onClear={() => setFiltros({})} />
        )}
        {lista.isLoading ? <p className="acta-empty">Cargando…</p> : lista.items.length === 0 ? (
          <p className="acta-empty">
            {tab === "pendientes" ? "Nada por autorizar: la bodega está al día." : "Todavía no hay órdenes de salida."}
          </p>
        ) : (
          <div className="tablewrap"><table className="notices-table">
            <thead>
              <tr>
                <th>Orden</th><th>Estado</th><th>Renglones</th><th>Necesaria</th><th>Pedida</th><th />
              </tr>
            </thead>
            <tbody>
              {lista.items.map((o) => (
                <tr key={o.id} className={o.status === "por_autorizar" ? "fin-overdue" : ""}>
                  <td>
                    <strong>{o.number ?? "Borrador sin número"}</strong>
                    <small>{o.location_name ?? "Bodega"}{o.note ? ` · ${o.note}` : ""}</small>
                  </td>
                  <td>
                    {cat?.release_statuses[o.status] ?? o.status}
                    {o.reject_reason && <small>Motivo: {o.reject_reason}</small>}
                    {o.shortage_note && <small>Al entregar: {o.shortage_note}</small>}
                  </td>
                  <td>
                    <details>
                      <summary>{o.lines.length} renglones</summary>
                      <ul>
                        {o.lines.map((l) => (
                          <li key={l.id}>
                            {l.item_name ?? "Artículo"}: {l.quantity_requested} {l.unit_label ?? ""}
                            {l.quantity_delivered !== null && ` — entregado ${l.quantity_delivered}`}
                            {l.spec_label ? ` (${l.spec_label})` : ""}
                          </li>
                        ))}
                      </ul>
                    </details>
                  </td>
                  <td>{o.needed_on ?? "—"}</td>
                  <td>{o.created_at ? o.created_at.slice(0, 10) : "—"}</td>
                  <td className="is-action">
                    {o.status === "borrador" && puedePedir && (
                      <button type="button" className="acta-link" disabled={enviar.isPending}
                        onClick={() => enviar.mutate(o.id)}>Enviar a autorizar</button>
                    )}
                    {o.status === "por_autorizar" && puedeAutorizar && (
                      <>
                        <button type="button" className="acta-link" disabled={autorizar.isPending}
                          onClick={() => autorizar.mutate(o.id)}>Autorizar</button>
                        <button type="button" className="acta-link"
                          onClick={() => setRechazando({ id: o.id, numero: o.number ?? "la salida" })}>Rechazar</button>
                      </>
                    )}
                    {o.status === "autorizada" && puedeEntregar && (
                      <button type="button" className="acta-link" disabled={entregar.isPending}
                        onClick={() => entregar.mutate(o.id)}>Entregar</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
        <PaginationControls {...lista.controls} />
      </article>
    </div>
  );
}

/** Lo que salió, lo que faltó y el aviso de que la obra ya lo tiene. */
function EntregaBanner({ resultado, onClose }: { resultado: DeliverResult; onClose: () => void }) {
  return (
    <div className={resultado.faltantes.length > 0 ? "warning-banner" : "info-banner"} role="status">
      <p>
        <strong>{resultado.number ?? "La salida"}</strong> quedó entregada
        {resultado.project_id ? " y lo entregado ya está en «Lo que la orden necesita» del proyecto." : "."}
      </p>
      {resultado.faltantes.length > 0 && (
        <>
          <p>No se pudo entregar todo:</p>
          <ul>{resultado.faltantes.map((f) => <li key={f.line_id}>{f.motivo}</li>)}</ul>
        </>
      )}
      <button type="button" className="acta-link" onClick={onClose}>Cerrar</button>
    </div>
  );
}

/**
 * Armar la orden. Todavía es un borrador: no tiene número ni mueve saldo hasta
 * que se manda a autorizar. Se puede partir de una lista predefinida (punto 2
 * del cuestionario) y de ahí ajustar cantidades, calibres y extras a mano.
 */
function ReleaseForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [projectId, setProjectId] = useState("");
  const [necesaria, setNecesaria] = useState("");
  const [nota, setNota] = useState("");
  const [lineas, setLineas] = useState<ReleaseLineInput[]>([{ item_id: "", quantity: "1", spec_label: "", notes: "" }]);
  const [deLista, setDeLista] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: articulos } = useQuery({
    queryKey: [...warehouseKeys.items, "para-salida"],
    queryFn: () => listItemsPage(1, 200, { active: true }).then((p) => p.items),
  });
  const { data: listas } = useQuery({
    queryKey: [...warehouseKeys.kits, "para-salida"],
    queryFn: () => listKitsPage(1, 200, { active: true }).then((p) => p.items),
  });
  const { data: proyectos } = useQuery({
    queryKey: ["projects", "para-salida"],
    queryFn: () => listProjectsPage(1, 200).then((p) => p.items),
  });

  const guardar = useMutation({
    mutationFn: () => createRelease({
      project_id: projectId || null,
      needed_on: necesaria || null,
      note: nota.trim() || null,
      lines: lineas.filter((l) => l.item_id).map((l) => ({
        item_id: l.item_id, quantity: l.quantity,
        spec_label: l.spec_label?.trim() || null, notes: l.notes?.trim() || null,
      })),
    }),
    onSuccess: onCreated,
    onError: (e) => setError(apiErrorMessage(e)),
  });

  function cambiar(i: number, campos: Partial<ReleaseLineInput>) {
    setLineas((actuales) => actuales.map((l, j) => (j === i ? { ...l, ...campos } : l)));
  }

  /** Copia los renglones de la lista encima de lo que ya hay escrito, sin repetir
   * el mismo material con el mismo calibre. */
  function aplicarLista(kitId: string) {
    const lista = (listas ?? []).find((k) => k.id === kitId);
    if (!lista) return;
    setLineas((actuales) => {
      const puestas = actuales.filter((l) => l.item_id);
      const claves = new Set(puestas.map((l) => `${l.item_id}|${l.spec_label ?? ""}`));
      const nuevas = lista.items
        .filter((r) => !claves.has(`${r.item_id}|${r.spec_label ?? ""}`))
        .map((r) => ({ item_id: r.item_id, quantity: r.quantity, spec_label: r.spec_label ?? "", notes: r.notes ?? "" }));
      return [...puestas, ...nuevas];
    });
    setDeLista(lista.name);
  }

  const renglones = lineas.filter((l) => l.item_id);

  return (
    <form className="acta fin-form fin-box" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <h3 className="acta-section-title">Nueva salida de bodega</h3>
      <p className="acta-lead">Queda como borrador: puedes revisarla y enviarla a autorizar cuando esté completa.</p>

      {(listas ?? []).length > 0 && (
        <div className="form-field">
          <label className="form-label" htmlFor="rel-lista">Aplicar una lista predefinida</label>
          <select id="rel-lista" value="" onChange={(e) => aplicarLista(e.target.value)}>
            <option value="">— Elegir una lista —</option>
            {(listas ?? []).map((k) => (
              <option key={k.id} value={k.id}>{k.name} ({k.items.length} renglones)</option>
            ))}
          </select>
          <small>
            {deLista
              ? `Se agregaron los renglones de «${deLista}». Ajústalos abajo: cada orden se queda con su copia.`
              : "Trae el material del tipo de trabajo; después se ajustan las cantidades y los calibres."}
          </small>
        </div>
      )}

      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="rel-obra">Obra (para cargar el material al proyecto)</label>
          <select id="rel-obra" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">Sin obra / uso interno</option>
            {(proyectos ?? []).map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="rel-fecha">Para cuándo se necesita</label>
          <input id="rel-fecha" type="date" value={necesaria} onChange={(e) => setNecesaria(e.target.value)} />
        </div>
      </div>

      <table className="materials-table">
        <thead>
          <tr><th scope="col">Artículo</th><th scope="col">Cantidad</th><th scope="col">Medida / calibre</th><th scope="col">Notas</th><th /></tr>
        </thead>
        <tbody>
          {lineas.map((l, i) => (
            <tr key={i}>
              <td>
                <select aria-label={`Artículo del renglón ${i + 1}`} value={l.item_id}
                  onChange={(e) => cambiar(i, { item_id: e.target.value })}>
                  <option value="">— Elegir —</option>
                  {(articulos ?? []).map((a) => (
                    <option key={a.id} value={a.id}>{a.name}{a.sku ? ` (${a.sku})` : ""}</option>
                  ))}
                </select>
              </td>
              <td>
                <input aria-label={`Cantidad del renglón ${i + 1}`} inputMode="decimal" value={l.quantity}
                  onChange={(e) => cambiar(i, { quantity: e.target.value })} />
              </td>
              <td>
                <input aria-label={`Medida del renglón ${i + 1}`} placeholder="1/4, 3/8, 12.000 BTU…"
                  value={l.spec_label ?? ""} onChange={(e) => cambiar(i, { spec_label: e.target.value })} />
              </td>
              <td>
                <input aria-label={`Notas del renglón ${i + 1}`} value={l.notes ?? ""}
                  onChange={(e) => cambiar(i, { notes: e.target.value })} />
              </td>
              <td>
                {lineas.length > 1 && (
                  <button type="button" className="acta-btn is-quiet"
                    onClick={() => setLineas((a) => a.filter((_, j) => j !== i))}>Quitar</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet"
          onClick={() => setLineas((a) => [...a, { item_id: "", quantity: "1", spec_label: "", notes: "" }])}>
          Agregar renglón
        </button>
      </div>

      <div className="form-field">
        <label className="form-label" htmlFor="rel-nota">Nota para quien entrega</label>
        <textarea id="rel-nota" rows={2} value={nota} onChange={(e) => setNota(e.target.value)} />
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending || renglones.length === 0}>
          {guardar.isPending ? "Guardando…" : "Guardar el borrador"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cancelar</button>
      </div>
    </form>
  );
}
