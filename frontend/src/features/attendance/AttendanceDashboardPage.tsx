import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/ui/PageHeader";
import { KpiCard } from "@/components/ui/KpiCard";
import { ageLabel, clockTime, getDashboard, getLive, hm, listPeople, SHIFT_STATUS_LABELS,
  type Dashboard } from "./api";
import { useMyAttendance } from "./useAttendance";
import "./attendance.css";

function iso(d: Date): string {
  return d.toLocaleDateString("en-CA");
}
function rango(tipo: string): [string, string] {
  const hoy = new Date();
  if (tipo === "hoy") return [iso(hoy), iso(hoy)];
  if (tipo === "semana") {
    const l = new Date(hoy);
    l.setDate(hoy.getDate() - ((hoy.getDay() + 6) % 7));
    const d = new Date(l);
    d.setDate(l.getDate() + 6);
    return [iso(l), iso(d)];
  }
  return [iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), iso(new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0))];
}

const COLORES = { programadas: "#98a2b3", registradas: "#2563eb", aprobadas: "#16845b" };

/** Barras por persona: programadas, registradas y aprobadas, lado a lado. */
function HoursByPerson({ rows }: { rows: Dashboard["by_person"] }) {
  if (!rows.length) return <p className="att-muted">Sin turnos ni marcaciones en el rango.</p>;
  const max = Math.max(60, ...rows.flatMap((r) => [r.scheduled_minutes, r.recorded_minutes, r.approved_minutes]));
  const alto = 22;
  const izq = 150;
  const ancho = 520;
  const h = rows.length * (alto * 3 + 14) + 30;
  return (
    <figure className="att-chart">
      <svg viewBox={`0 0 ${izq + ancho + 70} ${h}`} role="img"
        aria-label="Horas programadas, registradas y aprobadas por persona">
        {rows.map((r, i) => {
          const y = 10 + i * (alto * 3 + 14);
          const barras: [string, number, string][] = [["Programadas", r.scheduled_minutes, COLORES.programadas],
            ["Registradas", r.recorded_minutes, COLORES.registradas], ["Aprobadas", r.approved_minutes, COLORES.aprobadas]];
          return (
            <g key={r.user_id}>
              <text x={0} y={y + alto * 1.5 + 4} fontSize="13" fill="var(--ink)">{r.user_name.slice(0, 20)}</text>
              {barras.map(([nombre, v, c], j) => (
                <g key={nombre}>
                  <rect x={izq} y={y + j * alto} width={Math.max(1, (v / max) * ancho)} height={alto - 6} rx="3" fill={c}>
                    <title>{`${r.user_name} · ${nombre}: ${hm(v)}`}</title>
                  </rect>
                  <text x={izq + (v / max) * ancho + 6} y={y + j * alto + alto - 10} fontSize="11" fill="var(--ink-soft)">
                    {(v / 60).toFixed(1)} h</text>
                </g>
              ))}
            </g>
          );
        })}
      </svg>
      <figcaption className="att-legend">
        <span><i style={{ background: COLORES.programadas }} />Programadas</span>
        <span><i style={{ background: COLORES.registradas }} />Registradas</span>
        <span><i style={{ background: COLORES.aprobadas }} />Aprobadas</span>
      </figcaption>
    </figure>
  );
}

/** Línea de puntualidad: % de entradas a tiempo por día (solo días con entradas). */
function PunctualityLine({ points }: { points: Dashboard["punctuality"] }) {
  const con = points.filter((p) => p.pct != null);
  if (con.length < 2) return <p className="att-muted">Hace falta más de un día con entradas para ver la tendencia.</p>;
  const w = 640, h = 180, pad = 32;
  const x = (i: number) => pad + (i / Math.max(1, points.length - 1)) * (w - pad * 2);
  const y = (pct: number) => h - pad - (pct / 100) * (h - pad * 2);
  const linea = points.map((p, i) => (p.pct == null ? null : `${x(i)},${y(p.pct)}`)).filter(Boolean).join(" ");
  return (
    <figure className="att-chart">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Puntualidad por día">
        {[0, 50, 100].map((v) => (
          <g key={v}>
            <line x1={pad} x2={w - pad} y1={y(v)} y2={y(v)} stroke="var(--line)" />
            <text x={4} y={y(v) + 4} fontSize="11" fill="var(--ink-soft)">{v}%</text>
          </g>
        ))}
        <polyline points={linea} fill="none" stroke={COLORES.registradas} strokeWidth="2" />
        {points.map((p, i) => p.pct != null && (
          <circle key={p.date} cx={x(i)} cy={y(p.pct)} r="3.5" fill={COLORES.registradas}>
            <title>{`${p.date}: ${p.pct}% (${p.on_time} de ${p.with_entry})`}</title>
          </circle>
        ))}
        <text x={pad} y={h - 8} fontSize="11" fill="var(--ink-soft)">{points[0].date.slice(5)}</text>
        <text x={w - pad} y={h - 8} fontSize="11" fill="var(--ink-soft)" textAnchor="end">
          {points[points.length - 1].date.slice(5)}</text>
      </svg>
    </figure>
  );
}

/**
 * Panel de Don Aldo. Separa tres cosas: si el turno está activo, si hay
 * ubicación reciente y si el cumplimiento está verificado (aprobado). Una
 * persona sin señal no aparece como ausente.
 */
export function AttendanceDashboardPage() {
  const [tipo, setTipo] = useState("semana");
  const [persona, setPersona] = useState("");
  const [desde, hasta] = rango(tipo);
  const zona = useMyAttendance().data?.timezone;
  const { data: gente } = useQuery({ queryKey: ["attendance-people"], queryFn: listPeople });
  const { data, isLoading } = useQuery({ queryKey: ["attendance-dashboard", desde, hasta, persona],
    queryFn: () => getDashboard(desde, hasta, persona || undefined), refetchInterval: 30_000 });
  const { data: vivo } = useQuery({ queryKey: ["attendance-live"], queryFn: getLive, refetchInterval: 30_000 });
  const k = data?.kpis ?? {};
  const n = (key: string) => (k[key] ?? 0) as number;

  return (
    <div className="att-page is-wide">
      <PageHeader title="Panel de asistencia" description="Turnos, horas y cumplimiento de la malla. Se actualiza cada 30 segundos."
        actions={<Link className="att-btn" to="/payroll">Reporte de nómina</Link>} />
      <div className="att-filters">
        <div className="att-segment" role="group" aria-label="Rango">
          {[["hoy", "Hoy"], ["semana", "Esta semana"], ["mes", "Este mes"]].map(([v, l]) => (
            <button key={v} type="button" aria-pressed={tipo === v} className={tipo === v ? "is-on" : ""}
              onClick={() => setTipo(v)}>{l}</button>
          ))}
        </div>
        <label className="att-field">Persona
          <select value={persona} onChange={(e) => setPersona(e.target.value)}>
            <option value="">Todas</option>
            {(gente ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </select>
        </label>
      </div>

      <div className="att-kpis">
        <KpiCard label="Personal programado" value={n("scheduled_people")} loading={isLoading} />
        <KpiCard label="Turno iniciado" value={n("started")} loading={isLoading} />
        <KpiCard label="Pendiente de ingreso" value={n("pending_clock_in")} loading={isLoading}
          note="No es ausencia: aún puede marcar" />
        <KpiCard label="Llegadas tarde" value={n("late_arrivals")} loading={isLoading}
          note={`Tolerancia ${data?.settings.late_tolerance_minutes ?? 10} min`} />
        <KpiCard label="Salidas anticipadas" value={n("early_departures")} loading={isLoading} />
        <KpiCard label="Turnos completados" value={n("completed")} loading={isLoading} />
        <KpiCard label="Turnos incompletos" value={n("incomplete")} loading={isLoading} note="Sin salida, por regularizar" />
        <KpiCard label="Sin marcación" value={n("missed")} loading={isLoading} note="Turno vencido sin entrada" />
        <KpiCard label="Horas programadas" value={hm(n("scheduled_minutes"))} loading={isLoading} />
        <KpiCard label="Horas registradas" value={hm(n("recorded_minutes"))} loading={isLoading}
          note={n("open_minutes") ? `+ ${hm(n("open_minutes"))} en turnos abiertos` : "Turnos cerrados"} />
        <KpiCard label="Horas aprobadas" value={hm(n("approved_minutes"))} loading={isLoading} />
        <KpiCard label="Novedades pendientes" value={n("pending_novelties")} loading={isLoading} to="/attendance-review" />
        <KpiCard label="Cumplimiento de malla" value={k.compliance_pct == null ? "—" : `${k.compliance_pct}%`}
          loading={isLoading} note="Cumplidos ÷ turnos vencidos" />
        <KpiCard label="Marcas sin señal" value={n("offline_marks")} loading={isLoading} note="Hora del teléfono" />
      </div>

      <section className="att-card" aria-labelledby="att-vivo">
        <div className="att-card-head">
          <h2 id="att-vivo">Hoy, en vivo</h2>
          <Link to="/operations-map" className="att-btn">Ver en el mapa</Link>
        </div>
        <div className="att-scroll">
          <table className="att-table">
            <thead><tr><th>Persona</th><th>Turno</th><th>Estado del turno</th><th>Ubicación</th><th>Verificado</th></tr></thead>
            <tbody>
              {(vivo ?? []).map((f) => (
                <tr key={f.user_id}>
                  <th scope="row">{f.user_name}</th>
                  <td>{f.shift ? `${clockTime(f.shift.starts_at, zona)}–${clockTime(f.shift.ends_at, zona)}` : "Sin turno"}
                    {f.clock_in_at && <small> · entró {clockTime(f.clock_in_at, zona)}</small>}</td>
                  <td><span className={`att-pill is-${f.shift_status}`}>{SHIFT_STATUS_LABELS[f.shift_status] ?? f.shift_status}</span>
                    {f.paused && <small> · en pausa</small>}{f.offline && <small> · marcó sin señal</small>}</td>
                  <td>{f.location ? <span className={f.location.fresh ? "att-fresh" : "att-stale"}>
                    {f.location.fresh ? "Reciente" : "Última conocida"} · {ageLabel(f.location.age_minutes)}</span>
                    : <span className="att-muted">Sin ubicación</span>}</td>
                  <td>{f.verified ? "Aprobado" : f.entry_status === "closed" ? "Por aprobar" : "—"}</td>
                </tr>
              ))}
              {!vivo?.length && <tr><td colSpan={5} className="att-muted">Nadie tiene turno hoy.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <div className="att-two">
        <section className="att-card" aria-labelledby="att-por-persona">
          <h2 id="att-por-persona">Horas por persona</h2>
          {data && <HoursByPerson rows={data.by_person} />}
        </section>
        <section className="att-card" aria-labelledby="att-puntualidad">
          <h2 id="att-puntualidad">Puntualidad por día</h2>
          {data && <PunctualityLine points={data.punctuality} />}
          {data && (
            <div className="att-scroll">
              <table className="att-table">
                <thead><tr><th>Persona</th><th>Turnos</th><th>Tarde</th><th>Cumplimiento</th></tr></thead>
                <tbody>{data.by_person.map((r) => (
                  <tr key={r.user_id}><th scope="row">{r.user_name}</th><td>{r.shifts}</td><td>{r.late}</td>
                    <td>{r.compliance_pct == null ? "—" : `${r.compliance_pct}%`}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
