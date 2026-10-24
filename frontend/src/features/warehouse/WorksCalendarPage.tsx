import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "../finance/finance.css";
import { useAuth } from "@/features/auth/AuthContext";
import { localISODate, useInstallers } from "@/features/field-ops/module5Api";
import { apiClient } from "@/lib/apiClient";

/** Un turno: de cuándo a cuándo un técnico fue el responsable de la obra. */
interface Turno {
  project_id: string;
  project_title: string;
  project_status: string;
  technician_user_id: string;
  technician_name: string | null;
  started_on: string;
  ended_on: string | null;
}

/** Una jornada registrada en el diario de la obra. */
interface JornadaCal {
  id: string;
  project_id: string;
  project_title: string;
  log_date: string;
  technician_user_id: string | null;
  technician_name: string | null;
  helpers: { user_id: string; name: string | null }[];
  progress_note: string | null;
  work_done: string | null;
  next_day_plan: string | null;
}

interface Calendario {
  date_from: string;
  date_to: string;
  assignments: Turno[];
  day_logs: JornadaCal[];
}

const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const TONOS = 6;

function iso(d: Date): string {
  return localISODate(d);
}
function desdeIso(s: string): Date {
  return new Date(`${s}T12:00:00`);
}
function sumarDias(d: Date, n: number): Date {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
}
/** Lunes de la semana de `d`. */
function lunes(d: Date): Date {
  return sumarDias(d, -((d.getDay() + 6) % 7));
}
/** El mismo técnico siempre en el mismo color. */
function tono(id: string | null): number {
  let h = 0;
  for (const c of id ?? "") h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % TONOS;
}

/**
 * Calendario de obras (plan bodega-cierre, fase 5): quién estuvo en qué obra y
 * qué se hizo cada día. Sale de lo real: el turno de cada técnico responsable
 * (la «Orden liberada»; el personal rota) y las jornadas del diario, con sus
 * ayudantes. El técnico ve lo suyo; la oficina, todo y por técnico.
 */
export function WorksCalendarPage() {
  const { hasPermission } = useAuth();
  const oficina = hasPermission("projects.read_all");
  const { data: tecnicos } = useInstallers(hasPermission("dispatch.manage"));
  const [vista, setVista] = useState<"mes" | "semana">(() =>
    typeof window !== "undefined" && window.innerWidth < 768 ? "semana" : "mes");
  const [ancla, setAncla] = useState(() => new Date());
  const [tecnico, setTecnico] = useState("");

  // Mes: de lunes a domingo, cubriendo el mes completo. Semana: lunes a domingo.
  const { desde, hasta, dias } = useMemo(() => {
    const inicio = vista === "mes" ? lunes(new Date(ancla.getFullYear(), ancla.getMonth(), 1, 12)) : lunes(ancla);
    const fin = vista === "mes"
      ? sumarDias(lunes(new Date(ancla.getFullYear(), ancla.getMonth() + 1, 0, 12)), 6)
      : sumarDias(inicio, 6);
    const lista: Date[] = [];
    for (let d = inicio; d <= fin; d = sumarDias(d, 1)) lista.push(d);
    return { desde: iso(inicio), hasta: iso(fin), dias: lista };
  }, [vista, ancla]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["works-calendar", desde, hasta, tecnico],
    queryFn: async () => (await apiClient.get<Calendario>("/warehouse/calendar", {
      params: { date_from: desde, date_to: hasta, technician_user_id: tecnico || undefined },
    })).data,
  });

  const hoy = iso(new Date());
  const delDia = (dia: string) => {
    const jornadas = (data?.day_logs ?? []).filter((j) => j.log_date === dia);
    // El día en que un técnico toma la obra (la primera vez o cuando el personal
    // rota). Lo demás lo cuentan las jornadas: repetir el turno todos los días
    // llenaba el mes de lo mismo.
    const turnos = (data?.assignments ?? []).filter((t) => t.started_on === dia);
    return { jornadas, turnos };
  };

  function mover(paso: number) {
    setAncla((a) => vista === "mes" ? new Date(a.getFullYear(), a.getMonth() + paso, 1, 12) : sumarDias(a, 7 * paso));
  }
  const titulo = vista === "mes"
    ? ancla.toLocaleDateString("es-CO", { month: "long", year: "numeric" })
    : `Semana del ${desdeIso(desde).toLocaleDateString("es-CO", { day: "numeric", month: "short" })} al ${desdeIso(hasta).toLocaleDateString("es-CO", { day: "numeric", month: "short" })}`;
  const mesActual = ancla.getMonth();

  return (
    <div className="billing-page fin-page works-calendar">
      <header className="billing-head">
        <div>
          <h1>Calendario de obras</h1>
          <p>
            Quién estuvo en cada obra y qué se hizo cada día. Lo marcado es una jornada del diario; lo punteado,
            el día en que un técnico toma la obra (la primera vez o cuando cambia el responsable).
          </p>
        </div>
      </header>

      <div className="works-calendar-bar">
        <div className="works-calendar-nav">
          <button type="button" className="acta-btn is-quiet" onClick={() => mover(-1)} aria-label="Anterior">‹</button>
          <button type="button" className="acta-btn" onClick={() => setAncla(new Date())}>Hoy</button>
          <button type="button" className="acta-btn is-quiet" onClick={() => mover(1)} aria-label="Siguiente">›</button>
          <strong className="works-calendar-title">{titulo}</strong>
        </div>
        <div className="works-calendar-filters">
          <div className="billing-tabs" role="tablist" aria-label="Vista">
            {(["mes", "semana"] as const).map((v) => (
              <button key={v} type="button" role="tab" aria-selected={vista === v}
                className={`billing-tab${vista === v ? " is-active" : ""}`} onClick={() => setVista(v)}>
                {v === "mes" ? "Mes" : "Semana"}
              </button>
            ))}
          </div>
          {oficina && (tecnicos ?? []).length > 0 && (
            <select aria-label="Técnico" value={tecnico} onChange={(e) => setTecnico(e.target.value)}>
              <option value="">Todos los técnicos</option>
              {(tecnicos ?? []).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
            </select>
          )}
        </div>
      </div>

      {isError && <p className="form-error" role="alert">No se pudo cargar el calendario.</p>}
      {isLoading ? <p className="acta-empty">Cargando…</p> : (
        <div className={`works-calendar-grid is-${vista}`} role="grid" aria-label={titulo}>
          {DIAS.map((d) => <div key={d} className="works-calendar-head" role="columnheader">{d}</div>)}
          {dias.map((d) => {
            const dia = iso(d);
            const { jornadas, turnos } = delDia(dia);
            const vacio = jornadas.length === 0 && turnos.length === 0;
            return (
              <div key={dia} role="gridcell"
                className={["works-calendar-day", dia === hoy ? "is-today" : "",
                  vista === "mes" && d.getMonth() !== mesActual ? "is-other-month" : "", vacio ? "is-empty" : ""]
                  .filter(Boolean).join(" ")}>
                <span className="works-calendar-date">
                  <span className="works-calendar-weekday">{DIAS[(d.getDay() + 6) % 7]}</span> {d.getDate()}
                </span>
                {jornadas.map((j) => (
                  <Link key={j.id} to={`/projects/${j.project_id}`} className={`works-chip is-log is-t${tono(j.technician_user_id)}`}
                    title={[j.work_done, j.next_day_plan ? `Mañana: ${j.next_day_plan}` : null].filter(Boolean).join(" · ")}>
                    <strong>{j.project_title}</strong>
                    <span>
                      {j.technician_name ?? "Sin técnico"}
                      {j.helpers.length > 0 ? ` + ${j.helpers.map((h) => h.name ?? "").join(", ")}` : ""}
                    </span>
                    {j.progress_note && <small>{j.progress_note}</small>}
                  </Link>
                ))}
                {turnos.map((t) => (
                  <Link key={`${t.project_id}-${t.technician_user_id}`} to={`/projects/${t.project_id}`}
                    className={`works-chip is-turn is-t${tono(t.technician_user_id)}`}>
                    <strong>{t.project_title}</strong>
                    <span>{t.technician_name ?? "Técnico"} toma la obra</span>
                  </Link>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
