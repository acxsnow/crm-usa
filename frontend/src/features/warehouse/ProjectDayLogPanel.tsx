import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PaginationControls } from "@/components/PaginationControls";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage, localISODate, useInstallers } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { ItemPicker, useWarehouseItems } from "./ItemPicker";
import {
  listDayLogHelpers,
  saveDayLog,
  warehouseKeys,
  type DayLog,
  type DayLogMaterial,
  type WarehouseItem,
} from "./api";

const MONEDA = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const POR_PAGINA = 10;

function dinero(valor: string | null | undefined): string {
  if (!valor) return "—";
  return MONEDA.format(Number(valor));
}

/** «2026-10-21» → «miércoles, 21 de octubre». */
function diaLargo(iso: string | null): string {
  if (!iso) return "Sin fecha";
  return new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", {
    weekday: "long", day: "numeric", month: "long",
  });
}

/**
 * Diario de obra (punto 4 del cuestionario del 19 de octubre).
 *
 * «Los trabajos fuera de rebate duran varios días, con técnicos distintos cada
 * día». Aquí queda, día por día, quién trabajó, qué se hizo, hasta dónde se
 * avanzó, qué material salió y qué llevar al día siguiente. Más de una jornada
 * es una obra de varios días, y eso es lo que marca la Agenda.
 *
 * Los gastos del día no se digitan aquí: se leen de los gastos de la obra, que
 * es donde ya están cargados. El material que sale de una camioneta descuenta la
 * existencia y cuenta como costo de la obra.
 */
export function ProjectDayLogPanel({ projectId, soloLectura = false }: { projectId: string; soloLectura?: boolean }) {
  const { hasPermission, user } = useAuth();
  const qc = useQueryClient();
  // Quien ve la obra en solo lectura (fue el responsable antes o va de ayudante)
  // no registra; cada jornada la corrige su autor o la oficina.
  const puedeRegistrar = hasPermission("daylogs.manage") && !soloLectura;
  const oficina = hasPermission("projects.read_all");
  // Elegir a otro técnico exige el listado de despacho (`dispatch.manage`); sin
  // él, la jornada se registra a nombre de quien la escribe.
  const puedeElegirTecnico = hasPermission("dispatch.manage");
  const [editando, setEditando] = useState<DayLog | "nuevo" | null>(null);

  const lista = usePaginatedQuery<DayLog>({
    key: warehouseKeys.dayLogs(projectId),
    path: `/warehouse/projects/${projectId}/day-logs`,
    pageSize: POR_PAGINA,
  });

  /** Guardar la jornada mueve existencia y cambia el costo real de la obra. */
  function refrescar() {
    qc.invalidateQueries({ queryKey: warehouseKeys.dayLogs(projectId) });
    qc.invalidateQueries({ queryKey: warehouseKeys.budgetVsActual(projectId) });
    qc.invalidateQueries({ queryKey: warehouseKeys.projectBudget(projectId) });
    qc.invalidateQueries({ queryKey: warehouseKeys.stock });
    qc.invalidateQueries({ queryKey: warehouseKeys.movements });
    qc.invalidateQueries({ queryKey: warehouseKeys.items });
    // La Agenda marca las obras de varios días con el número de jornadas.
    qc.invalidateQueries({ queryKey: ["dispatch-agenda"] });
  }

  return (
    <section className="annex-section" aria-labelledby="anexo-diario">
      <div className="annex-section-head">
        <h3 id="anexo-diario">Diario de obra</h3>
        <span className="annex-count">
          {lista.total} {lista.total === 1 ? "jornada" : "jornadas"}
        </span>
      </div>
      <p className="acta-lead">
        Cada día, con su técnico: qué se hizo, hasta dónde se avanzó, qué material se usó, qué faltó y
        qué hay que llevar al día siguiente. Los gastos del día se leen de los gastos aprobados de la obra.
      </p>

      {editando ? (
        <DayLogForm
          projectId={projectId}
          initial={editando === "nuevo" ? null : editando}
          puedeElegirTecnico={puedeElegirTecnico}
          usuarioId={user?.id ?? ""}
          usuarioNombre={user?.full_name ?? null}
          onClose={() => setEditando(null)}
          onSaved={refrescar}
        />
      ) : (
        <>
          {puedeRegistrar && (
            <div className="acta-actions">
              <button type="button" className="acta-btn is-primary" onClick={() => setEditando("nuevo")}>
                Registrar la jornada
              </button>
            </div>
          )}

          {lista.isLoading ? (
            <p className="acta-empty">Cargando…</p>
          ) : lista.items.length === 0 ? (
            <p className="acta-empty">Esta obra todavía no tiene jornadas registradas.</p>
          ) : (
            <ul className="plain-list">
              {lista.items.map((jornada) => (
                <Jornada key={jornada.id} jornada={jornada}
                  onCorregir={puedeRegistrar && (oficina || jornada.created_by_user_id === user?.id)
                    ? () => setEditando(jornada) : undefined} />
              ))}
            </ul>
          )}
          <PaginationControls {...lista.controls} />
        </>
      )}
    </section>
  );
}

/** Una jornada, como se lee en el diario: el día, quién, qué y con qué. */
function Jornada({ jornada, onCorregir }: { jornada: DayLog; onCorregir?: () => void }) {
  const gastos = jornada.expenses;
  return (
    <li className="fin-box">
      <div className="fin-card-head">
        <strong>{diaLargo(jornada.log_date)}</strong>
        {onCorregir && (
          <button type="button" className="acta-link" onClick={onCorregir}>Corregir</button>
        )}
      </div>
      <p className="acta-lead">
        {jornada.technician_name ?? "Sin técnico asignado"}
        {jornada.helpers.length > 0 ? ` · Con: ${jornada.helpers.map((h) => h.name ?? "Técnico").join(", ")}` : ""}
        {jornada.crew ? ` · Cuadrilla: ${jornada.crew}` : ""}
        {jornada.hours ? ` · ${jornada.hours} h` : ""}
        {jornada.progress_note ? ` · Avance: ${jornada.progress_note}` : ""}
        {gastos.count > 0
          ? ` · Gastos del día: ${dinero(gastos.amount)} (${gastos.count} ${gastos.count === 1 ? "gasto" : "gastos"})`
          : " · Sin gastos aprobados ese día"}
      </p>

      <div className="fin-row">
        {etiquetado("Qué se hizo", jornada.work_done)}
        {etiquetado("Qué material faltó", jornada.missing_materials)}
        {etiquetado("Qué llevar al día siguiente", jornada.next_day_plan)}
        {etiquetado("Novedades del día", jornada.incidents)}
      </div>

      {jornada.materials.length === 0 ? (
        <p className="acta-empty">Ese día no se registró material.</p>
      ) : (
        <table className="materials-table">
          <thead>
            <tr>
              <th scope="col">Material del día</th>
              <th scope="col" className="is-num">Cantidad</th>
              <th scope="col">De dónde salió</th>
              <th scope="col">Bodega</th>
            </tr>
          </thead>
          <tbody>
            {jornada.materials.map((m) => (
              <tr key={m.id}>
                <td>
                  <strong>{m.description}</strong>
                  {m.sku && <small>Ref. {m.sku}</small>}
                </td>
                <td className="is-num">{m.quantity} {m.unit_label ?? ""}</td>
                <td>{m.location_name ?? "Comprado en la obra"}</td>
                <td>
                  <span className={`status-pill ${m.descontada ? "status-completed" : "status-pending"}`}>
                    {m.descontada ? "Descontado" : "Solo anotado"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </li>
  );
}

/** Un dato del día, solo si se escribió. */
function etiquetado(titulo: string, texto: string | null) {
  if (!texto) return null;
  return (
    <div className="form-field">
      <span className="form-label">{titulo}</span>
      <span className="acta-lead">{texto}</span>
    </div>
  );
}

/** Un renglón de material del formulario. */
interface FilaMaterial {
  id: string | null;
  /** Ya descontó la camioneta: el movimiento está en el libro y no se edita. */
  bloqueada: boolean;
  item_id: string;
  description: string;
  quantity: string;
  unit: string;
  location_id: string;
  /** Datos congelados, para mostrar la línea bloqueada tal como quedó. */
  location_name: string | null;
  unit_label: string | null;
}

function filaDe(m: DayLogMaterial): FilaMaterial {
  return {
    id: m.id, bloqueada: m.descontada, item_id: m.item_id ?? "", description: m.description,
    quantity: m.quantity, unit: m.unit ?? "", location_id: m.location_id ?? "",
    location_name: m.location_name, unit_label: m.unit_label,
  };
}

const FILA_VACIA: FilaMaterial = {
  id: null, bloqueada: false, item_id: "", description: "", quantity: "1", unit: "",
  location_id: "", location_name: null, unit_label: null,
};

/**
 * Registrar o corregir una jornada.
 *
 * El material que ya salió de la camioneta se muestra congelado: el libro de
 * movimientos no se toca, y para corregirlo se registra la devolución a bodega.
 * Lo que no movió existencia (la anotación del día) sí se edita.
 */
function DayLogForm({ projectId, initial, puedeElegirTecnico, usuarioId, usuarioNombre, onClose, onSaved }: {
  projectId: string;
  initial: DayLog | null;
  puedeElegirTecnico: boolean;
  usuarioId: string;
  usuarioNombre: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { data: tecnicos } = useInstallers(puedeElegirTecnico);
  const [fecha, setFecha] = useState(initial?.log_date ?? localISODate());
  const [tecnicoId, setTecnicoId] = useState(initial?.technician_user_id ?? (puedeElegirTecnico ? "" : usuarioId));
  const [cuadrilla, setCuadrilla] = useState(initial?.crew ?? "");
  const [horas, setHoras] = useState(initial?.hours ?? "");
  const [trabajo, setTrabajo] = useState(initial?.work_done ?? "");
  const [avance, setAvance] = useState(initial?.progress_note ?? "");
  const [faltante, setFaltante] = useState(initial?.missing_materials ?? "");
  const [siguiente, setSiguiente] = useState(initial?.next_day_plan ?? "");
  const [novedades, setNovedades] = useState(initial?.incidents ?? "");
  // Los técnicos que fueron con el responsable ese día: ven la obra, no la llenan.
  const [ayudantes, setAyudantes] = useState<string[]>(initial?.helpers.map((h) => h.user_id) ?? []);
  const { data: posiblesAyudantes } = useQuery({ queryKey: ["day-log-helpers"], queryFn: listDayLogHelpers,
    staleTime: 5 * 60_000 });
  const [filas, setFilas] = useState<FilaMaterial[]>(
    initial?.materials.length ? initial.materials.map(filaDe) : [{ ...FILA_VACIA }],
  );
  const [error, setError] = useState<string | null>(null);
  // Existencias de los artículos ya elegidos, para ofrecer de qué camioneta sale.
  const articulos = useWarehouseItems(filas.map((f) => f.item_id));

  const guardar = useMutation({
    mutationFn: () => saveDayLog(projectId, initial?.id ?? null, {
      log_date: fecha,
      technician_user_id: tecnicoId || null,
      crew: cuadrilla.trim() || null,
      hours: horas.trim() || null,
      work_done: trabajo.trim() || null,
      progress_note: avance.trim() || null,
      missing_materials: faltante.trim() || null,
      next_day_plan: siguiente.trim() || null,
      incidents: novedades.trim() || null,
      helper_user_ids: ayudantes.filter((a) => a !== tecnicoId),
      // Un renglón sin artículo y sin descripción es una línea que quedó en blanco.
      materials: filas
        .filter((f) => f.item_id || f.description.trim())
        .map((f) => ({
          id: f.id, item_id: f.item_id || null, description: f.description.trim() || null,
          quantity: f.quantity || "1", unit: f.unit || null, location_id: f.location_id || null,
        })),
    }),
    onSuccess: () => { onSaved(); onClose(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  function cambiar(i: number, campos: Partial<FilaMaterial>) {
    setFilas((actuales) => actuales.map((f, j) => (j === i ? { ...f, ...campos } : f)));
  }

  /** Al elegir el artículo se traen su nombre y su unidad del catálogo. */
  function elegirArticulo(i: number, articulo: WarehouseItem | null) {
    cambiar(i, {
      item_id: articulo?.id ?? "",
      description: articulo ? articulo.name : "",
      unit: articulo ? articulo.unit : "",
      // La ubicación se vuelve a elegir: la del artículo anterior no aplica.
      location_id: "",
    });
  }

  /** Dónde hay existencia del artículo elegido: la bodega o una camioneta. */
  function existencias(fila: FilaMaterial): WarehouseItem["by_location"] {
    return articulos[fila.item_id]?.by_location ?? [];
  }

  const hayBloqueadas = filas.some((f) => f.bloqueada);

  return (
    <div className="fin-form fin-box">
      <h3 className="acta-section-title">{initial ? "Corregir la jornada" : "Registrar la jornada"}</h3>
      <p className="acta-lead">
        Un día por obra. El material que sale de una camioneta descuenta la existencia y queda como costo
        de la obra; lo que se anota sin ubicación solo queda escrito en el diario.
      </p>

      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="diario-fecha">Día</label>
          <input id="diario-fecha" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} required />
        </div>
        {puedeElegirTecnico ? (
          <div className="form-field">
            <label className="form-label" htmlFor="diario-tecnico">Técnico del día</label>
            <select id="diario-tecnico" value={tecnicoId} onChange={(e) => setTecnicoId(e.target.value)}>
              <option value="">— Sin asignar —</option>
              {(tecnicos ?? []).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
            </select>
          </div>
        ) : (
          <div className="form-field">
            <span className="form-label">Técnico del día</span>
            <span className="acta-lead">La jornada queda a nombre de {usuarioNombre ?? "ti"}.</span>
          </div>
        )}
        {(posiblesAyudantes ?? []).length > 0 && (
          <fieldset className="form-field helpers-field">
            <legend className="form-label">Ayudantes <span className="optional">(técnicos que fueron contigo)</span></legend>
            <div className="helpers-options">
              {(posiblesAyudantes ?? []).filter((t) => t.id !== tecnicoId).map((t) => (
                <label key={t.id} className="billing-check">
                  <input type="checkbox" checked={ayudantes.includes(t.id)}
                    onChange={(e) => setAyudantes((a) => e.target.checked ? [...a, t.id] : a.filter((x) => x !== t.id))} />
                  {t.full_name}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        <div className="form-field">
          <label className="form-label" htmlFor="diario-cuadrilla">Cuadrilla <span className="optional">(opcional)</span></label>
          <input id="diario-cuadrilla" value={cuadrilla} maxLength={255} placeholder="Con quién se trabajó"
            onChange={(e) => setCuadrilla(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="diario-horas">Horas <span className="optional">(opcional)</span></label>
          <input id="diario-horas" inputMode="decimal" value={horas} placeholder="8"
            onChange={(e) => setHoras(e.target.value)} />
        </div>
      </div>

      <div className="form-field">
        <label className="form-label" htmlFor="diario-trabajo">Qué se hizo ese día</label>
        <textarea id="diario-trabajo" value={trabajo} maxLength={4000}
          onChange={(e) => setTrabajo(e.target.value)} />
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="diario-avance">Hasta dónde se avanzó <span className="optional">(opcional)</span></label>
        <input id="diario-avance" value={avance} maxLength={255} placeholder="Ej.: quedó montada la evaporadora"
          onChange={(e) => setAvance(e.target.value)} />
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="diario-faltante">Qué material faltó <span className="optional">(opcional)</span></label>
          <textarea id="diario-faltante" value={faltante} maxLength={4000}
            onChange={(e) => setFaltante(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="diario-siguiente">Qué llevar al día siguiente <span className="optional">(opcional)</span></label>
          <textarea id="diario-siguiente" value={siguiente} maxLength={4000}
            onChange={(e) => setSiguiente(e.target.value)} />
        </div>
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="diario-novedades">Novedades del día <span className="optional">(opcional)</span></label>
        <textarea id="diario-novedades" value={novedades} maxLength={4000}
          onChange={(e) => setNovedades(e.target.value)} />
      </div>

      <h4 className="acta-section-title">Material del día</h4>
      {hayBloqueadas && (
        <p className="acta-lead">
          Las líneas que ya descontaron la camioneta no se editan: el movimiento quedó en el libro de
          bodega. Para deshacerlo se registra la devolución a bodega.
        </p>
      )}
      <table className="materials-table">
        <thead>
          <tr>
            <th scope="col">Artículo</th>
            <th scope="col">Cantidad</th>
            <th scope="col">De dónde sale</th>
            <th scope="col">Descripción</th>
            <th aria-hidden="true" />
          </tr>
        </thead>
        <tbody>
          {filas.map((f, i) => f.bloqueada ? (
            <tr key={i}>
              <td><strong>{f.description}</strong><small>Ya descontó la camioneta</small></td>
              <td>{f.quantity} {f.unit_label ?? ""}</td>
              <td>{f.location_name ?? "—"}</td>
              <td>—</td>
              <td />
            </tr>
          ) : (
            <tr key={i}>
              <td>
                <ItemPicker label={`Artículo del material ${i + 1}`} itemId={f.item_id}
                  clearLabel={`Dejar sin artículo el material ${i + 1}`} onChange={(a) => elegirArticulo(i, a)} />
              </td>
              <td>
                <input aria-label={`Cantidad del material ${i + 1}`} inputMode="decimal" value={f.quantity}
                  onChange={(e) => cambiar(i, { quantity: e.target.value })} />
              </td>
              <td>
                <select aria-label={`De dónde sale el material ${i + 1}`} value={f.location_id}
                  disabled={!f.item_id} onChange={(e) => cambiar(i, { location_id: e.target.value })}>
                  <option value="">— Solo anotar —</option>
                  {existencias(f).map((l) => (
                    <option key={l.location_id} value={l.location_id}>{l.name}: {l.quantity}</option>
                  ))}
                </select>
              </td>
              <td>
                <input aria-label={`Descripción del material ${i + 1}`} value={f.description} maxLength={255}
                  placeholder={f.item_id ? "Del catálogo" : "Ej.: cinta de aluminio"}
                  onChange={(e) => cambiar(i, { description: e.target.value })} />
              </td>
              <td className="is-action">
                <button type="button" className="acta-btn is-quiet"
                  onClick={() => setFilas((a) => a.filter((_, j) => j !== i))}>Quitar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet"
          onClick={() => setFilas((a) => [...a, { ...FILA_VACIA }])}>Agregar material</button>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={guardar.isPending || !fecha}
          onClick={() => guardar.mutate()}>
          {guardar.isPending ? "Guardando…" : "Guardar la jornada"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cerrar</button>
      </div>
    </div>
  );
}
