import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/ui/PageHeader";
import { askText } from "@/components/ui/ConfirmDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { toast } from "@/lib/toast";
import { approveEntries, clockTime, correctEntry, getEntry, hm, listEntries, listNovelties, reviewNovelty,
  type Entry } from "./api";
import { useMyAttendance } from "./useAttendance";
import "./attendance.css";

function iso(d: Date): string {
  return d.toLocaleDateString("en-CA");
}
function apiError(e: unknown): string {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "No se pudo guardar.";
}
const EVENTOS: Record<string, string> = {
  clock_in: "Inicio de turno", clock_out: "Fin de turno", pause_start: "Pausa", pause_end: "Reanudó",
  en_route: "En camino", arrived: "Llegó", left_site: "Salió de obra", tracking: "Ubicación",
  login: "Inició sesión", logout: "Cerró sesión", connectivity_lost: "Perdió la señal",
  connectivity_restored: "Recuperó la señal", location_denied: "Negó la ubicación",
  location_unavailable: "Sin GPS",
};
const UBICACION: Record<string, string> = { ok: "con ubicación", denied: "permiso negado",
  unavailable: "sin GPS", timeout: "GPS tardó", not_requested: "", purged: "ubicación borrada (retención)" };

/** Lo que revisa Administración: novedades, marcaciones por aprobar y correcciones. */
export function AttendanceReviewPage() {
  const [tab, setTab] = useState<"novedades" | "marcaciones">("novedades");
  return (
    <div className="att-page is-wide">
      <PageHeader title="Novedades y horas" description="Aprueba novedades y horas, y corrige marcaciones. Cada cambio guarda el valor original." />
      <div className="att-segment" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "novedades"} className={tab === "novedades" ? "is-on" : ""}
          onClick={() => setTab("novedades")}>Novedades</button>
        <button type="button" role="tab" aria-selected={tab === "marcaciones"} className={tab === "marcaciones" ? "is-on" : ""}
          onClick={() => setTab("marcaciones")}>Marcaciones</button>
      </div>
      {tab === "novedades" ? <Novelties /> : <Entries />}
    </div>
  );
}

function Novelties() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const zona = useMyAttendance().data?.timezone;
  const [estado, setEstado] = useState("pending");
  const { data } = useQuery({ queryKey: ["novelties", estado], queryFn: () => listNovelties({ status: estado || undefined }) });
  const revisar = useMutation({
    mutationFn: ({ id, ok, nota }: { id: string; ok: boolean; nota?: string }) => reviewNovelty(id, ok, nota),
    onSuccess: (n) => { toast(n.status === "approved" ? "Novedad aprobada" : "Novedad rechazada");
      qc.invalidateQueries({ queryKey: ["novelties"] }); qc.invalidateQueries({ queryKey: ["entries"] }); },
    onError: (e) => toast(apiError(e)),
  });
  return (
    <section className="att-card">
      <label className="att-field">Estado
        <select value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="pending">Pendientes</option><option value="approved">Aprobadas</option>
          <option value="rejected">Rechazadas</option><option value="">Todas</option>
        </select>
      </label>
      {!(data ?? []).length && <p className="att-muted">No hay novedades.</p>}
      <ul className="att-cards">
        {(data ?? []).map((n) => (
          <li key={n.id} className="att-novelty">
            <div>
              <strong>{n.user_name}</strong> · {n.kind_label} · {n.work_date}
              {n.reason_name && <span className="att-muted"> · {n.reason_name}</span>}
            </div>
            {n.description && <p>{n.description}</p>}
            {(n.requested_clock_in_at || n.requested_clock_out_at) && (
              <p className="att-muted">Pide: entrada {clockTime(n.requested_clock_in_at, zona)} · salida {
                clockTime(n.requested_clock_out_at, zona)}</p>)}
            {n.status === "pending" ? (
              n.user_id === user?.id ? <p className="att-muted">Es tuya: la revisa otra persona.</p> : (
                <div className="att-actions">
                  <button type="button" className="att-btn" disabled={revisar.isPending} onClick={async () => {
                    const nota = await askText({ title: "Rechazar la novedad", label: "Motivo", required: true,
                      confirmLabel: "Rechazar", danger: true });
                    if (nota) revisar.mutate({ id: n.id, ok: false, nota });
                  }}>Rechazar</button>
                  <button type="button" className="att-btn is-primary" disabled={revisar.isPending}
                    onClick={() => revisar.mutate({ id: n.id, ok: true })}>Aprobar</button>
                </div>)
            ) : <p className="att-muted">{n.status === "approved" ? "Aprobada" : "Rechazada"} por {n.reviewed_by_name}
              {n.review_note ? `: ${n.review_note}` : ""}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Entries() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const zona = useMyAttendance().data?.timezone;
  const hoy = new Date();
  const [desde, setDesde] = useState(iso(new Date(hoy.getTime() - 6 * 864e5)));
  const [hasta, setHasta] = useState(iso(hoy));
  const [estado, setEstado] = useState("closed");
  const [marcadas, setMarcadas] = useState<string[]>([]);
  const [abierta, setAbierta] = useState<string | null>(null);
  const { data } = useQuery({ queryKey: ["entries", desde, hasta, estado],
    queryFn: () => listEntries({ date_from: desde, date_to: hasta, status: estado || undefined }) });
  const aprobar = useMutation({
    mutationFn: () => approveEntries(marcadas),
    onSuccess: (r) => {
      toast(`${r.approved.length} aprobadas${r.errors.length ? `, ${r.errors.length} no: ${r.errors[0].message}` : ""}`);
      setMarcadas([]);
      qc.invalidateQueries({ queryKey: ["entries"] });
    },
  });
  const ajenas = (data ?? []).filter((e) => e.user_id !== user?.id && e.status === "closed");
  return (
    <section className="att-card">
      <div className="att-filters">
        <label className="att-field">Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
        <label className="att-field">Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
        <label className="att-field">Estado
          <select value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="closed">Por aprobar</option><option value="open">Abiertas (sin salida)</option>
            <option value="approved">Aprobadas</option><option value="">Todas</option>
          </select>
        </label>
        {estado === "closed" && (
          <button type="button" className="att-btn is-primary" disabled={!marcadas.length || aprobar.isPending}
            onClick={() => aprobar.mutate()}>Aprobar {marcadas.length || ""}</button>
        )}
      </div>
      <div className="att-scroll">
        <table className="att-table">
          <thead><tr>
            {estado === "closed" && <th><input type="checkbox" aria-label="Marcar todas"
              checked={!!ajenas.length && marcadas.length === ajenas.length}
              onChange={(e) => setMarcadas(e.target.checked ? ajenas.map((x) => x.id) : [])} /></th>}
            <th>Persona</th><th>Día</th><th>Entrada</th><th>Salida</th><th>Pausas</th><th>Efectivas</th><th>Estado</th><th />
          </tr></thead>
          <tbody>
            {(data ?? []).map((e) => (
              <EntryRow key={e.id} e={e} zona={zona} conCheck={estado === "closed"} propia={e.user_id === user?.id}
                marcada={marcadas.includes(e.id)} abierta={abierta === e.id}
                onCheck={(v) => setMarcadas(v ? [...marcadas, e.id] : marcadas.filter((x) => x !== e.id))}
                onToggle={() => setAbierta(abierta === e.id ? null : e.id)} />
            ))}
            {!(data ?? []).length && <tr><td colSpan={9} className="att-muted">Sin marcaciones en el rango.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EntryRow({ e, zona, conCheck, propia, marcada, abierta, onCheck, onToggle }: {
  e: Entry; zona?: string; conCheck: boolean; propia: boolean; marcada: boolean; abierta: boolean;
  onCheck: (v: boolean) => void; onToggle: () => void;
}) {
  return (
    <>
      <tr>
        {conCheck && <td>{!propia && <input type="checkbox" checked={marcada} aria-label={`Marcar ${e.user_name}`}
          onChange={(ev) => onCheck(ev.target.checked)} />}</td>}
        <th scope="row">{e.user_name}</th>
        <td>{e.work_date}</td>
        <td>{clockTime(e.clock_in_at, zona)}{e.clock_in_offline && <small> · sin señal</small>}</td>
        <td>{clockTime(e.clock_out_at, zona)}{e.closed_by === "admin" && <small> · regularizada</small>}</td>
        <td>{hm(e.pause_minutes)}</td>
        <td>{hm(e.status === "approved" ? e.approved_minutes : e.effective_minutes)}</td>
        <td><span className={`att-pill is-${e.status}`}>{e.status === "approved" ? "Aprobada"
          : e.status === "closed" ? "Por aprobar" : "Abierta"}</span></td>
        <td><button type="button" className="att-btn is-link" onClick={onToggle}>{abierta ? "Cerrar" : "Detalle"}</button></td>
      </tr>
      {abierta && <tr><td colSpan={9}><EntryDetailPanel id={e.id} zona={zona} propia={propia} /></td></tr>}
    </>
  );
}

function EntryDetailPanel({ id, zona, propia }: { id: string; zona?: string; propia: boolean }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["entry", id], queryFn: () => getEntry(id) });
  const [entrada, setEntrada] = useState("");
  const [salida, setSalida] = useState("");
  const [motivo, setMotivo] = useState("");
  const corregir = useMutation({
    mutationFn: () => correctEntry(id, {
      clock_in_at: entrada ? new Date(entrada).toISOString() : null,
      clock_out_at: salida ? new Date(salida).toISOString() : null, reason: motivo }),
    onSuccess: () => { toast("Marcación corregida"); setMotivo(""); qc.invalidateQueries({ queryKey: ["entry", id] });
      qc.invalidateQueries({ queryKey: ["entries"] }); },
    onError: (err) => toast(apiError(err)),
  });
  if (!data) return <p>Cargando…</p>;
  return (
    <div className="att-detail">
      <h3>Bitácora</h3>
      <ol className="att-timeline">
        {data.events.map((ev) => (
          <li key={ev.id}><strong>{clockTime(ev.occurred_at, zona)}</strong> {EVENTOS[ev.event_type] ?? ev.event_type}
            {UBICACION[ev.location_status] ? ` · ${UBICACION[ev.location_status]}` : ""}
            {ev.distance_km != null && ` · ${ev.distance_km.toFixed(1)} km estimados en línea recta`}
            {ev.offline && ` · enviada sin señal (llegó ${clockTime(ev.received_at, zona)})`}
            {ev.note && <em> · {ev.note}</em>}</li>
        ))}
      </ol>
      {!!data.corrections.length && (
        <>
          <h3>Correcciones</h3>
          <ul className="att-list">{data.corrections.map((c, i) => (
            <li key={i}>{new Date(c.at).toLocaleString("es-US", { timeZone: zona })} · {c.by}: {c.reason}
              <br /><small>Antes: entrada {clockTime(String(c.before.clock_in_at ?? ""), zona)}, salida {
                clockTime((c.before.clock_out_at as string) ?? null, zona)} → Después: entrada {
                clockTime(String(c.after.clock_in_at ?? ""), zona)}, salida {clockTime((c.after.clock_out_at as string) ?? null, zona)}</small></li>
          ))}</ul>
        </>
      )}
      {!propia && data.status !== "approved" && (
        <form className="att-form" onSubmit={(ev) => { ev.preventDefault(); corregir.mutate(); }}>
          <h3>Corregir</h3>
          <div className="att-form-row">
            <label>Entrada<input type="datetime-local" value={entrada} onChange={(ev) => setEntrada(ev.target.value)} /></label>
            <label>Salida<input type="datetime-local" value={salida} onChange={(ev) => setSalida(ev.target.value)} /></label>
          </div>
          <label>Motivo (obligatorio)<input value={motivo} required maxLength={2000} onChange={(ev) => setMotivo(ev.target.value)} /></label>
          <div className="att-actions"><button type="submit" className="att-btn is-primary"
            disabled={!motivo.trim() || (!entrada && !salida) || corregir.isPending}>Guardar corrección</button></div>
        </form>
      )}
    </div>
  );
}
