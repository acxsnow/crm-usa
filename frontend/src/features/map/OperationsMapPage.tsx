import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/features/auth/AuthContext";
import { apiClient } from "@/lib/apiClient";
import { toast } from "@/lib/toast";
import { ageLabel, getMapPeople, getMapProjects, getMapRoute, listPeople, setProjectLocation,
  type MapProject } from "@/features/attendance/api";
import { LeafletMap, type MapLine, type MapMarker } from "./LeafletMap";
import "@/features/attendance/attendance.css";

const ESTADOS: Record<string, string> = { planning: "Planeación", scheduled: "Agendada", in_progress: "En curso",
  completed: "Terminada", cancelled: "Cancelada" };
const TONO: Record<string, MapMarker["tone"]> = { planning: "muted", scheduled: "info", in_progress: "warn",
  completed: "ok", cancelled: "muted" };

function iniciales(nombre: string): string {
  return nombre.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("");
}

/** Las obras del día según el calendario de obras (`GET /warehouse/calendar`), sin calendario paralelo. */
async function calendarProjectIds(dia: string): Promise<string[]> {
  const r = await apiClient.get<{ assignments: { project_id: string; started_on: string }[];
    day_logs: { project_id: string; log_date: string }[] }>("/warehouse/calendar", { params: { date_from: dia, date_to: dia } });
  return [...new Set([...r.data.day_logs.filter((l) => l.log_date === dia).map((l) => l.project_id),
    ...r.data.assignments.filter((a) => a.started_on === dia).map((a) => a.project_id)])];
}

/**
 * Mapa operativo: el personal en su última ubicación conocida (con su
 * antigüedad siempre a la vista), las obras como pines por estado, el día del
 * calendario y el orden sugerido de paradas de una persona.
 */
export function OperationsMapPage() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const [params] = useSearchParams();
  const veGente = hasPermission("locations.view");
  const veCalendario = ["projects.read_all", "dispatch.manage", "daylogs.manage"].some((p) => hasPermission(p));
  const puedeUbicar = hasPermission("projects.update");
  const [dia, setDia] = useState(params.get("date") ?? new Date().toLocaleDateString("en-CA"));
  const [modo, setModo] = useState<"abiertas" | "dia">(params.get("date") ? "dia" : "abiertas");
  const [persona, setPersona] = useState("");
  const [cliente, setCliente] = useState("");
  const [estado, setEstado] = useState("");
  const [ubicando, setUbicando] = useState<MapProject | null>(null);
  const [ruta, setRuta] = useState(false);

  const { data: gente } = useQuery({ queryKey: ["attendance-people"], queryFn: listPeople, enabled: veGente });
  const { data: ubicaciones } = useQuery({ queryKey: ["map-people"], queryFn: getMapPeople, refetchInterval: 30_000 });
  const { data: idsCalendario } = useQuery({ queryKey: ["map-calendar", dia], queryFn: () => calendarProjectIds(dia),
    enabled: modo === "dia" && veCalendario });
  const { data: obras } = useQuery({
    queryKey: ["map-projects", modo, dia, persona, cliente, estado, idsCalendario],
    queryFn: async () => {
      const base = { technician_user_id: persona || undefined, customer: cliente || undefined, status: estado || undefined };
      if (modo === "abiertas") return getMapProjects(base);
      const [delDia, delCal] = await Promise.all([getMapProjects({ ...base, on_date: dia }),
        idsCalendario?.length ? getMapProjects({ ...base, ids: idsCalendario }) : Promise.resolve({ projects: [], unlocated: [] })]);
      const unir = (a: MapProject[], b: MapProject[]) => [...new Map([...a, ...b].map((p) => [p.id, p])).values()];
      return { projects: unir(delDia.projects, delCal.projects), unlocated: unir(delDia.unlocated, delCal.unlocated) };
    },
  });
  const { data: recorrido } = useQuery({ queryKey: ["map-route", dia, persona], queryFn: () => getMapRoute(dia, persona || undefined),
    enabled: ruta && (!!persona || !veGente) });

  const fijar = useMutation({
    mutationFn: ({ id, lat, lng }: { id: string; lat: number; lng: number }) => setProjectLocation(id, lat, lng),
    onSuccess: () => { toast("Ubicación de la obra guardada"); setUbicando(null); qc.invalidateQueries({ queryKey: ["map-projects"] }); },
    onError: () => toast("No se pudo guardar la ubicación."),
  });

  const { markers, lines } = useMemo(() => {
    const ms: MapMarker[] = [];
    const ls: MapLine[] = [];
    for (const p of obras?.projects ?? []) {
      if (p.latitude == null || p.longitude == null) continue;
      ms.push({ id: `p-${p.id}`, lat: p.latitude, lng: p.longitude, kind: "project", tone: TONO[p.status] ?? "info",
        lines: [p.title, p.customer_name, p.address, `${ESTADOS[p.status] ?? p.status}${p.technician_name ? ` · ${p.technician_name}` : ""}`],
        link: { href: `/projects/${p.id}`, label: "Abrir obra" } });
    }
    for (const u of ubicaciones ?? []) {
      if (persona && u.user_id !== persona) continue;
      ms.push({ id: `u-${u.user_id}`, lat: u.latitude, lng: u.longitude, kind: "person", badge: iniciales(u.user_name),
        tone: u.fresh ? "ok" : "muted",
        lines: [u.user_name, `${u.fresh ? "Ubicación reciente" : "Última ubicación conocida"} · ${ageLabel(u.age_minutes)}`,
          u.shift_open ? "Turno abierto" : "Sin turno abierto", u.accuracy_m ? `Precisión ±${Math.round(u.accuracy_m)} m` : ""]
          .filter(Boolean) });
    }
    if (ruta && recorrido) {
      let previo: [number, number] | null = recorrido.origin ? [recorrido.origin.latitude, recorrido.origin.longitude] : null;
      recorrido.stops.forEach((s, i) => {
        if (s.latitude == null || s.longitude == null) return;
        const aqui: [number, number] = [s.latitude, s.longitude];
        ms.push({ id: `r-${s.id}`, lat: s.latitude, lng: s.longitude, kind: "origin", badge: String(i + 1), tone: "brand",
          lines: [`Parada ${i + 1}: ${s.title}`, s.address, s.km_from_previous != null ? `${s.km_from_previous} km en línea recta` : ""]
            .filter(Boolean) });
        if (previo) ls.push({ id: `l-${s.id}`, from: previo, to: aqui, dashed: true });
        previo = aqui;
      });
    }
    return { markers: ms, lines: ls };
  }, [obras, ubicaciones, persona, ruta, recorrido]);

  return (
    <div className="att-page is-wide">
      <PageHeader title="Mapa operativo" description="Personal en su última ubicación conocida y obras por estado. Se actualiza cada 30 segundos." />
      <div className="att-filters">
        <div className="att-segment" role="group" aria-label="Qué obras">
          <button type="button" aria-pressed={modo === "abiertas"} className={modo === "abiertas" ? "is-on" : ""}
            onClick={() => setModo("abiertas")}>Obras abiertas</button>
          <button type="button" aria-pressed={modo === "dia"} className={modo === "dia" ? "is-on" : ""}
            onClick={() => setModo("dia")}>Día del calendario</button>
        </div>
        {(modo === "dia" || ruta) && <label className="att-field">Día<input type="date" value={dia} onChange={(e) => setDia(e.target.value)} /></label>}
        {veGente && (
          <label className="att-field">Persona
            <select value={persona} onChange={(e) => setPersona(e.target.value)}>
              <option value="">Todas</option>
              {(gente ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
            </select>
          </label>
        )}
        <label className="att-field">Cliente<input value={cliente} maxLength={100} onChange={(e) => setCliente(e.target.value)}
          placeholder="Nombre del cliente" /></label>
        <label className="att-field">Estado
          <select value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="">{modo === "abiertas" ? "Abiertas" : "Todos"}</option>
            {Object.entries(ESTADOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="att-check"><input type="checkbox" checked={ruta} onChange={(e) => setRuta(e.target.checked)} />
          Orden sugerido del día</label>
      </div>

      {ubicando && (
        <p className="att-banner is-info" role="status">Toca el mapa donde está «{ubicando.title}».
          <button type="button" className="att-btn is-link" onClick={() => setUbicando(null)}>Cancelar</button></p>
      )}
      <LeafletMap label="Mapa operativo" markers={markers} lines={lines} height="min(68vh, 620px)" fit={!ubicando}
        onMapClick={ubicando ? (lat, lng) => fijar.mutate({ id: ubicando.id, lat, lng }) : undefined} />

      <div className="att-legend">
        <span><i className="map-dot tone-ok" />Persona, ubicación reciente (menos de 15 min)</span>
        <span><i className="map-dot tone-muted" />Persona, última ubicación conocida</span>
        <span><i className="map-dot tone-info" />Obra agendada</span>
        <span><i className="map-dot tone-warn" />Obra en curso</span>
      </div>

      {ruta && (
        <section className="att-card" aria-labelledby="att-ruta">
          <h2 id="att-ruta">Orden sugerido del día</h2>
          {veGente && !persona ? <p className="att-muted">Elige una persona.</p> : recorrido ? (
            <>
              <p className="att-muted">Por distancia en línea recta desde su última ubicación, no por tiempo de manejo.
                Total estimado: <strong>{recorrido.total_km} km</strong>.</p>
              <ol className="att-list">{recorrido.stops.map((s) => (
                <li key={s.id}>{s.title} <span className="att-muted">· {s.address || "sin dirección"}
                  {s.km_from_previous != null ? ` · ${s.km_from_previous} km` : " · sin coordenadas"}</span></li>))}</ol>
              {!recorrido.stops.length && <p className="att-muted">No tiene obras ese día.</p>}
              {recorrido.directions_url && <a className="att-btn is-primary" href={recorrido.directions_url} target="_blank"
                rel="noreferrer noopener">Abrir la ruta en Google Maps</a>}
            </>
          ) : <p>Calculando…</p>}
        </section>
      )}

      {!!obras?.unlocated.length && (
        <section className="att-card" aria-labelledby="att-sin-ubicar">
          <h2 id="att-sin-ubicar">Obras sin ubicar ({obras.unlocated.length})</h2>
          <p className="att-muted">No tienen coordenadas de la visita.{puedeUbicar ? " Toca «Fijar en el mapa» y luego el punto." : ""}</p>
          <ul className="att-list">{obras.unlocated.map((p) => (
            <li key={p.id}><a href={`/projects/${p.id}`}>{p.title}</a> <span className="att-muted">· {p.address || "sin dirección"}</span>
              {puedeUbicar && <button type="button" className="att-btn is-link" onClick={() => setUbicando(p)}>Fijar en el mapa</button>}</li>
          ))}</ul>
        </section>
      )}
    </div>
  );
}
