import { Fragment, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, ExpandToggle, PaginatedTable, RowAction, RowActions } from "@/components/DataTable";
import { SearchPicker } from "@/components/SearchPicker";
import { askText } from "@/components/ui/ConfirmDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { getProject, listProjectsPage } from "@/features/field-ops/api";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { useSearchTextFromUrl } from "@/lib/useSearchTextFromUrl";
import type { Project } from "@/types/fieldOps";
import { ItemPicker } from "./ItemPicker";
import {
  approveRelease,
  createRelease,
  deliverRelease,
  serialKeys,
  type DeliverLineInput,
  listKitsPage,
  rejectRelease,
  cancelRelease,
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
  // Desde el buscador global (?q=SAL-…): la búsqueda va sobre todas las salidas.
  useSearchTextFromUrl((q) => { setTab("todas"); setFiltros((f) => ({ ...f, q })); });
  // «Pedir material a bodega» desde la obra llega con ?nueva=1&obra=<id>.
  const [enlace] = useSearchParams();
  const navigate = useNavigate();
  const obraDeLaFicha = enlace.get("nueva") ? enlace.get("obra") : null;
  const [creando, setCreando] = useState(Boolean(enlace.get("nueva")));
  // Rechazar (quien autoriza) y anular (quien la pidió o bodega) piden motivo
  // en el mismo formulario.
  const [rechazando, setRechazando] = useState<{ id: string; numero: string; anular?: boolean } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [entrega, setEntrega] = useState<DeliverResult | null>(null);
  const [entregando, setEntregando] = useState<WarehouseRelease | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });

  const pendientes = usePaginatedQuery<WarehouseRelease>({
    key: warehouseKeys.pendingReleases, path: "/warehouse/releases/pending", pageSize: PAGE_SIZE,
    enabled: puedeAutorizar && tab === "pendientes",
  });

  const params = { status: filtros.status || undefined, q: filtros.q || undefined };
  const todas = usePaginatedQuery<WarehouseRelease>({
    key: warehouseKeys.releases, path: "/warehouse/releases", pageSize: PAGE_SIZE,
    params, enabled: tab === "todas",
  });

  const campos: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Número (SAL-…) o nota" },
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
    mutationFn: () => (rechazando?.anular ? cancelRelease : rejectRelease)(rechazando?.id as string, motivo.trim()),
    onSuccess: () => { setError(null); setRechazando(null); setMotivo(""); invalidarBodega(qc); },
    onError: alFallar,
  });
  const entregar = useMutation({
    mutationFn: ({ id, lines }: { id: string; lines: DeliverLineInput[] }) =>
      deliverRelease(id, null, lines),
    onSuccess: (r) => {
      setError(null); setEntrega(r); setEntregando(null); invalidarBodega(qc);
      qc.invalidateQueries({ queryKey: serialKeys.all });
    },
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
          obraInicial={obraDeLaFicha}
          onClose={() => { setCreando(false); if (obraDeLaFicha) navigate(`/projects/${obraDeLaFicha}`); }}
          onCreated={() => {
            setCreando(false); setTab("todas"); invalidarBodega(qc);
            // Si vino desde la obra, vuelve a ella: ahí se ve la salida pedida.
            if (obraDeLaFicha) navigate(`/projects/${obraDeLaFicha}`);
          }}
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
          <h3 className="acta-section-title">{rechazando.anular ? "Anular" : "Rechazar"} {rechazando.numero}</h3>
          <p className="acta-lead">{rechazando.anular
            ? "La salida queda anulada y no se puede autorizar ni entregar. No mueve existencias: nada salió de bodega."
            : "El técnico recibe el motivo, así que conviene decir qué falta o por qué no se autoriza."}</p>
          <div className="form-field">
            <label className="form-label" htmlFor="rel-motivo">Motivo</label>
            <textarea id="rel-motivo" rows={2} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </div>
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={rechazar.isPending || !motivo.trim()}>
              {rechazar.isPending ? "Guardando…" : rechazando.anular ? "Anular la salida" : "Rechazar la salida"}
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
        <PaginatedTable list={lista} getRowKey={(o) => o.id} className="release-orders"
          emptyMessage={tab === "pendientes" ? "Nada por autorizar: la bodega está al día." : "Todavía no hay órdenes de salida."}
          rowClassName={(o) => (o.status === "por_autorizar" ? "fin-overdue" : undefined)}
          expandable={{
            // La orden del técnico ya entregada, con cosas por cargar, se abre sola («Lo llevo»).
            defaultExpanded: (o) => o.status === "entregada" && esMia(o) && (o.loading?.loaded ?? 0) < (o.loading?.loadable ?? 0),
            render: (o) => (
              <OrderLines orden={o} marcable={o.status === "entregada" && esMia(o)}
                onMarcar={(l, loaded) => cargar.mutateAsync({ id: o.id, lineId: l.id, loaded })} />
            ),
          }}
          columns={[
            { key: "orden", header: "Orden", render: (o) => (
              <>
                <strong>{o.number ?? "Borrador sin número"}</strong>
                {o.project_title && <small>{o.project_title}</small>}
                <small>
                  {o.technician_name ? `Para ${o.technician_name}` : (o.location_name ?? "Bodega")}
                  {o.requested_by_name && o.requested_by_name !== o.technician_name ? ` · pidió ${o.requested_by_name}` : ""}
                </small>
                {o.note && <small>{o.note}</small>}
              </>
            ) },
            { key: "estado", header: "Estado", render: (o) => (
              <>
                {cat?.release_statuses[o.status] ?? o.status}
                {o.reject_reason && <small>Motivo: {o.reject_reason}</small>}
                {o.cancel_reason && <small>Anulada: {o.cancel_reason}</small>}
                {o.shortage_note && <small>Al entregar: {o.shortage_note}</small>}
                {o.loading && o.loading.loadable > 0 && (
                  <small className={o.loading.required_pending > 0 ? "release-load is-pending" : "release-load"}>
                    Cargado {o.loading.loaded} de {o.loading.loadable}
                    {o.loading.required_pending === 1 && " · falta 1 obligatorio"}
                    {o.loading.required_pending > 1 && ` · faltan ${o.loading.required_pending} obligatorios`}
                  </small>
                )}
              </>
            ) },
            { key: "renglones", header: "Renglones", render: (o, fila) => (
              <>
                <ExpandToggle expanded={fila.expanded} onToggle={fila.toggle}>
                  {o.lines.length} {o.lines.length === 1 ? "renglón" : "renglones"}
                </ExpandToggle>
                {o.omissions.length > 0 && (
                  <small>{o.omissions.length === 1 ? "1 obligatorio quitado" : `${o.omissions.length} obligatorios quitados`}</small>
                )}
              </>
            ) },
            { key: "necesaria", header: "Necesaria", render: (o) => o.needed_on ?? "—" },
            { key: "pedida", header: "Pedida", render: (o) => (o.created_at ? o.created_at.slice(0, 10) : "—") },
            { key: "acciones", header: "", render: (o) => (
              <RowActions>
                {o.status === "borrador" && puedePedir && (
                  <RowAction variant="primary" disabled={enviar.isPending} onClick={() => enviar.mutate(o.id)}>Enviar a autorizar</RowAction>
                )}
                {o.status === "por_autorizar" && puedeAutorizar && (
                  <>
                    <RowAction variant="primary" disabled={autorizar.isPending} onClick={() => autorizar.mutate(o.id)}>Autorizar</RowAction>
                    <RowAction onClick={() => { setRechazando({ id: o.id, numero: o.number ?? "la salida" }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                      Rechazar</RowAction>
                  </>
                )}
                {o.status === "autorizada" && puedeEntregar && (
                  <RowAction variant="primary" disabled={entregar.isPending} onClick={() => setEntregando(o)}>Entregar</RowAction>
                )}
                {["borrador", "por_autorizar", "autorizada"].includes(o.status)
                  && (o.requested_by_user_id === user?.id || hasPermission("warehouse.manage")) && (
                  <RowAction variant="danger" onClick={() => {
                    setMotivo(""); setRechazando({ id: o.id, numero: o.number ?? "el borrador", anular: true });
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}>Anular</RowAction>
                )}
              </RowActions>
            ) },
          ]} />
      </article>
    </div>
  );
}

/** «1.00» → «1», «2.50» → «2.5»: en la lista de renglones no hacen falta los ceros. */
const cantidad = (valor: string | number) => Number(valor).toLocaleString("es-CO", { maximumFractionDigits: 2 });

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
                  <strong>{l.item_name ?? "Artículo"}</strong>{l.spec_label ? ` (${l.spec_label})` : ""}
                  <span className="release-qty">
                    {cantidad(l.quantity_requested)} {l.unit_label ?? ""}
                    {l.quantity_delivered !== null && ` · entregado ${cantidad(l.quantity_delivered)}`}
                  </span>
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

/** Cuántos seriales pide un renglón con serial: uno por unidad que sale. */
const MAX_SERIALES = 50;
function unidadesConSerial(cantidad: string): number {
  const n = Number(cantidad);
  return Number.isInteger(n) && n > 0 ? Math.min(n, MAX_SERIALES) : 0;
}

/**
 * Entregar renglón por renglón: Bodega confirma cuánto sale de cada uno (de 0
 * a lo pedido). Lo que no sale queda como faltante con su motivo. Un equipo
 * con serial sale por unidades enteras, con el serial de cada una (D-007).
 */
function DeliveryForm({ orden, enviando, onCancel, onSubmit }: {
  orden: WarehouseRelease;
  enviando: boolean;
  onCancel: () => void;
  onSubmit: (lines: DeliverLineInput[]) => void;
}) {
  const [cantidades, setCantidades] = useState<Record<string, string>>(
    () => Object.fromEntries(orden.lines.map((l) => [l.id, l.quantity_requested])));
  const [seriales, setSeriales] = useState<Record<string, string[]>>({});
  const serialesDe = (lineId: string, n: number) =>
    Array.from({ length: n }, (_, i) => seriales[lineId]?.[i] ?? "");
  const cambiarSerial = (lineId: string, i: number, valor: string) => {
    const lista = [...(seriales[lineId] ?? [])];
    lista[i] = valor;
    setSeriales({ ...seriales, [lineId]: lista });
  };
  const cantidadMala = orden.lines.some((l) => {
    const n = Number(cantidades[l.id]);
    return cantidades[l.id] === "" || Number.isNaN(n) || n < 0 || n > Number(l.quantity_requested)
      || (l.has_serial && !Number.isInteger(n));
  });
  const serialMalo = orden.lines.some((l) => {
    if (!l.has_serial) return false;
    const lista = serialesDe(l.id, unidadesConSerial(cantidades[l.id])).map((s) => s.trim().toUpperCase());
    return lista.some((s) => !s) || new Set(lista).size !== lista.length;
  });
  const invalida = cantidadMala || serialMalo;
  return (
    <form className="acta fin-form fin-box"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(orden.lines.map((l) => ({
          line_id: l.id, quantity: cantidades[l.id],
          ...(l.has_serial ? { serials: serialesDe(l.id, unidadesConSerial(cantidades[l.id])).map((s) => s.trim()) } : {}),
        })));
      }}>
      <h3 className="acta-section-title">Entregar {orden.number ?? "la salida"}</h3>
      <p className="acta-lead">
        Confirma cuánto sale de cada renglón. Si en bodega hay menos, se entrega lo que hay y la diferencia queda
        como faltante.
      </p>
      <DataTable rows={orden.lines} isLoading={false} getRowKey={(l) => l.id}
        columns={[
          { key: "articulo", header: "Artículo", render: (l) => (
            <>
              <strong>{l.item_name ?? "Artículo"}</strong>
              <small>{[l.spec_label, l.section].filter(Boolean).join(" · ")}</small>
              {l.is_required && <span className="billing-chip is-required">Obligatorio</span>}
            </>
          ) },
          { key: "pedido", header: "Pedido", className: "is-num", render: (l) => `${l.quantity_requested} ${l.unit_label ?? ""}` },
          { key: "sale", header: "Sale", render: (l) => (
            <>
              <input aria-label={`Cantidad que sale de ${l.item_name ?? "el renglón"}`} inputMode="decimal"
                value={cantidades[l.id]} onChange={(e) => setCantidades({ ...cantidades, [l.id]: e.target.value })} />
              {l.has_serial && unidadesConSerial(cantidades[l.id]) > 0 && (
                <div className="serial-inputs">
                  <small>Serial de cada unidad</small>
                  {serialesDe(l.id, unidadesConSerial(cantidades[l.id])).map((serial, n) => (
                    <input key={n} aria-label={`Serial ${n + 1} de ${l.item_name ?? "el equipo"}`}
                      autoCapitalize="characters" autoComplete="off" spellCheck={false} placeholder={`Serial ${n + 1}`}
                      value={serial} onChange={(e) => cambiarSerial(l.id, n, e.target.value)} />
                  ))}
                </div>
              )}
            </>
          ) },
        ]} />
      {cantidadMala && (
        <p className="form-error" role="alert">
          Cada cantidad va de 0 a lo pedido; un equipo con serial sale por unidades enteras.
        </p>
      )}
      {!cantidadMala && serialMalo && (
        <p className="form-error" role="alert">Anota un serial distinto para cada unidad con serial que sale.</p>
      )}
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
      {resultado.lines.some((l) => l.serials.length > 0) && (
        <p>
          Seriales entregados:{" "}
          {resultado.lines.filter((l) => l.serials.length > 0)
            .map((l) => `${l.item_name ?? "Equipo"}: ${l.serials.join(", ")}`).join(" · ")}
        </p>
      )}
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
function ReleaseForm({ obraInicial, onClose, onCreated }: {
  obraInicial?: string | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [obra, setObra] = useState<Project | null>(null);
  // Desde la ficha de la obra: la obra ya viene puesta.
  const { data: obraPedida } = useQuery({
    queryKey: ["project", obraInicial],
    queryFn: () => getProject(obraInicial as string),
    enabled: Boolean(obraInicial),
  });
  useEffect(() => {
    if (obraPedida) setObra((actual) => actual ?? obraPedida);
  }, [obraPedida]);
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

  // «Guardar y enviar a autorizar» es lo normal cuando ya se eligió todo: el
  // borrador solo existe para seguir armándola después.
  const [enviarYa, setEnviarYa] = useState(false);
  const guardar = useMutation({
    mutationFn: async () => {
      const creada = await crearOrden();
      return enviarYa ? submitRelease(creada.id) : creada;
    },
    onSuccess: onCreated,
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const crearOrden = () => createRelease({
      project_id: obra?.id ?? null,
      needed_on: necesaria || null,
      note: nota.trim() || null,
      lines: lineas.filter((l) => l.item_id).map((l) => ({
        item_id: l.item_id, quantity: l.quantity,
        spec_label: l.spec_label?.trim() || null, notes: l.notes?.trim() || null,
        origin: l.origin ?? "manual", section: l.section?.trim() || null, is_required: !!l.is_required,
      })),
      omissions: omisiones.map((o) => ({ item_id: o.item_id, spec_label: o.spec_label || null, reason: o.reason })),
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

      <DataTable rows={lineas.map((l, i) => ({ ...l, i }))} isLoading={false} getRowKey={(l) => l.clave}
        groupBy={(l) => l.section}
        columns={[
          { key: "articulo", header: "Artículo", render: (l) => (
            <>
              <ItemPicker label={`Artículo del renglón ${l.i + 1}`} itemId={l.item_id}
                onChange={(a) => cambiar(l.i, { item_id: a?.id ?? "", nombre: a?.name })} />
              {l.is_required && <span className="billing-chip is-required">Obligatorio</span>}
            </>
          ) },
          { key: "cantidad", header: "Cantidad", render: (l) => (
            <input aria-label={`Cantidad del renglón ${l.i + 1}`} inputMode="decimal" value={l.quantity}
              onChange={(e) => cambiar(l.i, { quantity: e.target.value })} />
          ) },
          { key: "medida", header: "Medida / calibre", render: (l) => (
            <input aria-label={`Medida del renglón ${l.i + 1}`} placeholder="1/4, 3/8, 12.000 BTU…"
              value={l.spec_label ?? ""} onChange={(e) => cambiar(l.i, { spec_label: e.target.value })} />
          ) },
          { key: "notas", header: "Notas", render: (l) => (
            <input aria-label={`Notas del renglón ${l.i + 1}`} value={l.notes ?? ""}
              onChange={(e) => cambiar(l.i, { notes: e.target.value })} />
          ) },
          { key: "acciones", header: "", render: (l) => (lineas.length > 1 || l.item_id) && (
            <RowActions><RowAction variant="danger" onClick={() => quitar(l.i)}>Quitar</RowAction></RowActions>
          ) },
        ]} />
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
        <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending || renglones.length === 0}
          onClick={() => setEnviarYa(true)}>
          {guardar.isPending && enviarYa ? "Enviando…" : "Guardar y enviar a autorizar"}
        </button>
        <button type="submit" className="acta-btn" disabled={guardar.isPending || renglones.length === 0}
          onClick={() => setEnviarYa(false)}>
          {guardar.isPending && !enviarYa ? "Guardando…" : "Guardar el borrador"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cancelar</button>
      </div>
    </form>
  );
}
