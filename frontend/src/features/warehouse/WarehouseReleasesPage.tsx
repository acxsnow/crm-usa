import { Fragment, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { PaginationControls } from "@/components/PaginationControls";
import { SearchPicker } from "@/components/SearchPicker";
import { askText } from "@/components/ui/ConfirmDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { listProjectsPage } from "@/features/field-ops/api";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import type { Project } from "@/types/fieldOps";
import { ItemPicker } from "./ItemPicker";
import {
  approveRelease,
  createRelease,
  deliverRelease,
  listKitsPage,
  rejectRelease,
  submitRelease,
  warehouseCatalogs,
  warehouseKeys,
  loadReleaseLine,
  type DeliverResult,
  type ReleaseLine,
  type ReleaseLineInput,
  type ReleaseOmission,
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
  const { hasPermission, user } = useAuth();
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
  const [entregando, setEntregando] = useState<WarehouseRelease | null>(null);
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
    mutationFn: ({ id, lines }: { id: string; lines: { line_id: string; quantity: string }[] }) =>
      deliverRelease(id, null, lines),
    onSuccess: (r) => { setError(null); setEntrega(r); setEntregando(null); invalidarBodega(qc); },
    onError: alFallar,
  });
  const cargar = useMutation({
    mutationFn: ({ id, lineId, loaded }: { id: string; lineId: string; loaded: boolean }) =>
      loadReleaseLine(id, lineId, loaded),
    meta: { silent: true },
    onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: warehouseKeys.releases }); },
    onError: alFallar,
  });
  /** La checklist «lo llevo» es del técnico de la orden (o de quien la pidió). */
  const esMia = (o: WarehouseRelease) =>
    Boolean(user) && (o.technician_user_id === user?.id || o.requested_by_user_id === user?.id);

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

      {entregando && (
        <DeliveryForm orden={entregando} enviando={entregar.isPending} onCancel={() => setEntregando(null)}
          onSubmit={(lines) => entregar.mutate({ id: entregando.id, lines })} />
      )}

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
          <div className="tablewrap"><table className="notices-table release-orders">
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
                    {o.loading && o.loading.loadable > 0 && (
                      <small className={o.loading.required_pending > 0 ? "release-load is-pending" : "release-load"}>
                        Cargado {o.loading.loaded} de {o.loading.loadable}
                        {o.loading.required_pending === 1 && " · falta 1 obligatorio"}
                        {o.loading.required_pending > 1 && ` · faltan ${o.loading.required_pending} obligatorios`}
                      </small>
                    )}
                  </td>
                  <td>
                    <details open={o.status === "entregada" && esMia(o) && (o.loading?.loaded ?? 0) < (o.loading?.loadable ?? 0)}>
                      <summary>
                        {o.lines.length} {o.lines.length === 1 ? "renglón" : "renglones"}
                        {o.omissions.length === 1 && " · 1 obligatorio quitado"}
                        {o.omissions.length > 1 && ` · ${o.omissions.length} obligatorios quitados`}
                      </summary>
                      <OrderLines orden={o}
                        marcable={o.status === "entregada" && esMia(o)}
                        onMarcar={(l, loaded) => cargar.mutateAsync({ id: o.id, lineId: l.id, loaded })} />
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
                        onClick={() => setEntregando(o)}>Entregar</button>
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

/**
 * Los renglones de una orden, por sección, con lo obligatorio marcado. En una
 * orden entregada que es del técnico, cada renglón entregado tiene su «Lo
 * llevo»: es la checklist al cargar la camioneta (plan bodega-cierre, fase 2).
 */
function OrderLines({ orden, marcable, onMarcar }: {
  orden: WarehouseRelease;
  marcable: boolean;
  onMarcar: (linea: ReleaseLine, loaded: boolean) => Promise<unknown>;
}) {
  // La casilla cambia al tocarla, sin esperar al servidor: con la señal de los
  // parques, esperar la respuesta se siente como que no tomó. Si falla, vuelve.
  const [marcas, setMarcas] = useState<Record<string, boolean>>({});
  async function marcar(l: ReleaseLine, valor: boolean) {
    setMarcas((m) => ({ ...m, [l.id]: valor }));
    try {
      await onMarcar(l, valor);
    } catch {
      setMarcas((m) => { const copia = { ...m }; delete copia[l.id]; return copia; });
    }
  }
  return (
    <div className="release-lines">
      <ul>
        {orden.lines.map((l, i) => {
          const entregado = l.quantity_delivered !== null && Number(l.quantity_delivered) > 0;
          const nuevaSeccion = l.section && l.section !== (i > 0 ? orden.lines[i - 1].section : null);
          return (
            <Fragment key={l.id}>
              {nuevaSeccion && <li className="release-lines-section">{l.section}</li>}
              <li className={l.loaded ? "is-loaded" : undefined}>
                {marcable && entregado ? (
                  <label className="release-load-check">
                    <input type="checkbox" checked={l.id in marcas ? marcas[l.id] : l.loaded}
                      onChange={(e) => marcar(l, e.target.checked)} />
                    <span>Lo llevo</span>
                  </label>
                ) : null}
                <span className="release-line-text">
                  <strong>{l.item_name ?? "Artículo"}</strong>{l.spec_label ? ` (${l.spec_label})` : ""}:{" "}
                  {l.quantity_requested} {l.unit_label ?? ""}
                  {l.quantity_delivered !== null && ` — entregado ${l.quantity_delivered}`}
                  {l.is_required && <span className="billing-chip is-required">Obligatorio</span>}
                </span>
              </li>
            </Fragment>
          );
        })}
      </ul>
      {orden.omissions.length > 0 && (
        <div className="release-omissions">
          <strong>Obligatorios que no se llevan:</strong>
          <ul>
            {orden.omissions.map((o) => (
              <li key={`${o.item_id}-${o.spec_label ?? ""}`}>
                {o.item_name ?? "Artículo"}{o.spec_label ? ` (${o.spec_label})` : ""}: {o.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Entregar renglón por renglón: Bodega confirma cuánto sale de cada uno (de 0
 * a lo pedido). Lo que no sale queda como faltante con su motivo.
 */
function DeliveryForm({ orden, enviando, onCancel, onSubmit }: {
  orden: WarehouseRelease;
  enviando: boolean;
  onCancel: () => void;
  onSubmit: (lines: { line_id: string; quantity: string }[]) => void;
}) {
  const [cantidades, setCantidades] = useState<Record<string, string>>(
    () => Object.fromEntries(orden.lines.map((l) => [l.id, l.quantity_requested])));
  const invalida = orden.lines.some((l) => {
    const n = Number(cantidades[l.id]);
    return cantidades[l.id] === "" || Number.isNaN(n) || n < 0 || n > Number(l.quantity_requested);
  });
  return (
    <form className="acta fin-form fin-box"
      onSubmit={(e) => { e.preventDefault(); onSubmit(orden.lines.map((l) => ({ line_id: l.id, quantity: cantidades[l.id] }))); }}>
      <h3 className="acta-section-title">Entregar {orden.number ?? "la salida"}</h3>
      <p className="acta-lead">
        Confirma cuánto sale de cada renglón. Si en bodega hay menos, se entrega lo que hay y la diferencia queda
        como faltante.
      </p>
      <table className="materials-table">
        <thead><tr><th scope="col">Artículo</th><th scope="col" className="is-num">Pedido</th><th scope="col">Sale</th></tr></thead>
        <tbody>
          {orden.lines.map((l) => (
            <tr key={l.id}>
              <td>
                <strong>{l.item_name ?? "Artículo"}</strong>
                <small>{[l.spec_label, l.section].filter(Boolean).join(" · ")}</small>
                {l.is_required && <span className="billing-chip is-required">Obligatorio</span>}
              </td>
              <td className="is-num">{l.quantity_requested} {l.unit_label ?? ""}</td>
              <td>
                <input aria-label={`Cantidad que sale de ${l.item_name ?? "el renglón"}`} inputMode="decimal"
                  value={cantidades[l.id]} onChange={(e) => setCantidades({ ...cantidades, [l.id]: e.target.value })} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {invalida && <p className="form-error" role="alert">Cada cantidad va de 0 a lo pedido.</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={enviando || invalida}>
          {enviando ? "Entregando…" : "Entregar"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
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

/** Un renglón del formulario: lo que se manda más el nombre (para el motivo) y
 * una clave estable, para que quitar un renglón no le pase a otro el buscador. */
type FilaSalida = ReleaseLineInput & { clave: string; nombre?: string };

let contadorFilas = 0;
const nuevaClave = () => `fila-${++contadorFilas}`;
const FILA_VACIA: Omit<FilaSalida, "clave"> = { item_id: "", quantity: "1", spec_label: "", notes: "" };

/**
 * Armar la orden. Todavía es un borrador: no tiene número ni mueve saldo hasta
 * que se manda a autorizar. Se puede partir de una lista predefinida (punto 2
 * del cuestionario) y de ahí ajustar cantidades, calibres y extras a mano.
 */
function ReleaseForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [obra, setObra] = useState<Project | null>(null);
  const [necesaria, setNecesaria] = useState("");
  const [nota, setNota] = useState("");
  const [lineas, setLineas] = useState<FilaSalida[]>(() => [{ ...FILA_VACIA, clave: nuevaClave() }]);
  // Obligatorios de la lista que se quitaron, con el motivo: quien autoriza los ve.
  const [omisiones, setOmisiones] = useState<(ReleaseOmission & { fila: FilaSalida })[]>([]);
  const [deLista, setDeLista] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: listas } = useQuery({
    queryKey: [...warehouseKeys.kits, "para-salida"],
    queryFn: () => listKitsPage(1, 200, { active: true }).then((p) => p.items),
  });

  const guardar = useMutation({
    mutationFn: () => createRelease({
      project_id: obra?.id ?? null,
      needed_on: necesaria || null,
      note: nota.trim() || null,
      lines: lineas.filter((l) => l.item_id).map((l) => ({
        item_id: l.item_id, quantity: l.quantity,
        spec_label: l.spec_label?.trim() || null, notes: l.notes?.trim() || null,
        origin: l.origin ?? "manual", section: l.section?.trim() || null, is_required: !!l.is_required,
      })),
      omissions: omisiones.map((o) => ({ item_id: o.item_id, spec_label: o.spec_label || null, reason: o.reason })),
    }),
    onSuccess: onCreated,
    onError: (e) => setError(apiErrorMessage(e)),
  });

  function cambiar(i: number, campos: Partial<FilaSalida>) {
    setLineas((actuales) => actuales.map((l, j) => (j === i ? { ...l, ...campos } : l)));
  }

  /** Quitar un renglón. Si es obligatorio de la lista, pide el motivo: es la
   * checklist que pidió el dueño para que no se olvide nada. */
  async function quitar(i: number) {
    const fila = lineas[i];
    if (fila.is_required && fila.item_id) {
      const motivo = await askText({
        title: `¿Por qué no se lleva «${fila.nombre ?? "este artículo"}»?`,
        message: "Es obligatorio en la lista. El motivo queda en la orden y lo ve quien autoriza.",
        label: "Motivo", required: true, placeholder: "Ej.: ya hay en la camioneta",
        confirmLabel: "Quitar", cancelLabel: "Dejarlo",
      });
      if (!motivo?.trim()) return;
      setOmisiones((a) => [...a, { item_id: fila.item_id, item_name: fila.nombre, spec_label: fila.spec_label,
        reason: motivo.trim(), fila }]);
    }
    setLineas((a) => {
      const quedan = a.filter((_, j) => j !== i);
      return quedan.length ? quedan : [{ ...FILA_VACIA, clave: nuevaClave() }];
    });
  }

  /** Deshacer: el obligatorio vuelve a la orden y se borra su motivo. */
  function devolver(k: number) {
    const omision = omisiones[k];
    setOmisiones((a) => a.filter((_, j) => j !== k));
    setLineas((a) => [...a.filter((l) => l.item_id), omision.fila]);
  }

  /** Copia los renglones de la lista encima de lo que ya hay escrito, sin repetir
   * el mismo material con el mismo calibre. */
  function aplicarLista(kitId: string) {
    const lista = (listas ?? []).find((k) => k.id === kitId);
    if (!lista) return;
    setLineas((actuales) => {
      const puestas = actuales.filter((l) => l.item_id);
      const claves = new Set(puestas.map((l) => `${l.item_id}|${l.spec_label ?? ""}`));
      const nuevas: FilaSalida[] = lista.items
        .filter((r) => !claves.has(`${r.item_id}|${r.spec_label ?? ""}`))
        .map((r) => ({ item_id: r.item_id, quantity: r.quantity, spec_label: r.spec_label ?? "", notes: r.notes ?? "",
          origin: "lista", section: r.section ?? "", is_required: r.is_required, nombre: r.item_name ?? undefined,
          clave: nuevaClave() }));
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
          <span className="form-label">Obra (para cargar el material al proyecto)</span>
          <SearchPicker<Project>
            label="Obra"
            value={obra}
            onChange={setObra}
            search={(q) => listProjectsPage(1, 20, q ? { q } : {}).then((p) => p.items)}
            queryKey={["projects", "buscador-salida"]}
            getKey={(p) => p.id}
            getLabel={(p) => p.title}
            renderOption={(p) => (
              <>
                <strong>{p.title}</strong>
                <small>{[p.address_street, p.address_city].filter(Boolean).join(", ")}</small>
              </>
            )}
            pageSize={20}
            placeholder="Busca la obra (vacío = uso interno)"
            clearLabel="Quitar la obra"
          />
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
            <Fragment key={l.clave}>
            {(l.section || "") !== (i > 0 ? lineas[i - 1].section || "" : "") && l.section && (
              <tr className="release-section-row"><th colSpan={5} scope="colgroup">{l.section}</th></tr>
            )}
            <tr>
              <td>
                <ItemPicker label={`Artículo del renglón ${i + 1}`} itemId={l.item_id}
                  onChange={(a) => cambiar(i, { item_id: a?.id ?? "", nombre: a?.name })} />
                {l.is_required && <span className="billing-chip is-required">Obligatorio</span>}
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
                {(lineas.length > 1 || l.item_id) && (
                  <button type="button" className="acta-btn is-quiet" onClick={() => quitar(i)}>Quitar</button>
                )}
              </td>
            </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet"
          onClick={() => setLineas((a) => [...a, { ...FILA_VACIA, clave: nuevaClave() }])}>
          Agregar renglón
        </button>
      </div>

      {omisiones.length > 0 && (
        <div className="warning-banner" role="status">
          <p><strong>Obligatorios que no se llevan</strong> (los ve quien autoriza):</p>
          <ul>
            {omisiones.map((o, k) => (
              <li key={o.fila.clave}>
                {o.item_name ?? "Artículo"}{o.spec_label ? ` (${o.spec_label})` : ""}: {o.reason}{" "}
                <button type="button" className="acta-link" onClick={() => devolver(k)}>Volver a agregarlo</button>
              </li>
            ))}
          </ul>
        </div>
      )}

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
