import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/ui/PageHeader";
import { clockTime, getClockOutSummary, hm, listMyEntries, listMyShifts, SHIFT_STATUS_LABELS,
  type ClockOutSummary } from "./api";
import { NoveltyForm } from "./NoveltyForm";
import { ME_KEY, useMark, useMyAttendance, usePendingMarks } from "./useAttendance";
import "./attendance.css";

function isoDia(d: Date): string {
  return d.toLocaleDateString("en-CA");
}

/**
 * «Mi turno»: el reloj del turno, en camino / llegué / salida de obra, pausas,
 * novedades y FINALIZAR TURNO con su resumen. Pensada para el celular en el
 * parque, con botones grandes.
 */
export function MyShiftPage() {
  const qc = useQueryClient();
  const { data: me, isLoading } = useMyAttendance();
  const { run, busy } = useMark();
  const pendientes = usePendingMarks();
  const [params, setParams] = useSearchParams();
  const [obra, setObra] = useState("");
  const [motivoPausa, setMotivoPausa] = useState("");
  const [resumen, setResumen] = useState<ClockOutSummary | null>(null);
  const [nota, setNota] = useState("");
  const [novedad, setNovedad] = useState(false);
  const [, tick] = useState(0);

  const hoy = new Date();
  const desde = isoDia(new Date(hoy.getTime() - 13 * 864e5));
  const hasta = isoDia(new Date(hoy.getTime() + 6 * 864e5));
  const { data: entradas } = useQuery({ queryKey: ["my-entries", desde], queryFn: () => listMyEntries(desde, isoDia(hoy)) });
  const { data: turnos } = useQuery({ queryKey: ["my-shifts", desde], queryFn: () => listMyShifts(isoDia(hoy), hasta) });

  // El reloj del turno avanza solo cada 30 s; los datos se refrescan cada minuto.
  useEffect(() => {
    const t = window.setInterval(() => tick((n) => n + 1), 30_000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    if (!obra && me?.projects_today?.length) setObra(me.shift_project?.id ?? me.projects_today[0].id);
  }, [me, obra]);

  const abrirResumen = async () => {
    try {
      setResumen(await getClockOutSummary());
    } catch {
      setResumen(null);
    }
  };
  useEffect(() => {
    if (params.get("finalizar") === "1" && me?.entry?.status === "open" && !resumen) {
      void abrirResumen();
      params.delete("finalizar");
      setParams(params, { replace: true });
    }
  }, [params, me, resumen, setParams]);

  if (isLoading) return <div className="att-page"><p>Cargando tu turno…</p></div>;
  if (!me) return <div className="att-page"><p>No se pudo cargar tu turno.</p></div>;

  const zona = me.timezone;
  const entry = me.entry;
  const abierta = entry?.status === "open";
  const transcurrido = entry ? Math.max(0, Math.floor((Date.now() - new Date(entry.clock_in_at).getTime()) / 60000)) : 0;
  // Las pausas vienen del servidor (se refrescan cada minuto).
  const efectivas = entry ? transcurrido - entry.pause_minutes : 0;

  return (
    <div className="att-page">
      <PageHeader title="Mi turno" description="Marca tu entrada, tus desplazamientos y tu salida." />
      {pendientes > 0 && (
        <p className="att-banner is-warn" role="status">
          {pendientes === 1 ? "1 marca sin enviar" : `${pendientes} marcas sin enviar`}: se enviarán solas cuando vuelva la señal.
        </p>
      )}

      <section className="att-card att-clock" aria-label="Estado del turno">
        {abierta && entry ? (
          <>
            <p className="att-eyebrow">{entry.paused ? "En pausa" : "En turno"} desde {clockTime(entry.clock_in_at, zona)}
              {entry.clock_in_offline && " · marcado sin señal"}</p>
            <strong className="att-clock-big">{hm(Math.max(0, efectivas))}</strong>
            <p className="att-muted">Horas efectivas · pausas {hm(entry.pause_minutes)}</p>
          </>
        ) : (
          <>
            <p className="att-eyebrow">Sin turno iniciado</p>
            <strong className="att-clock-big">{clockTime(me.server_time, zona)}</strong>
            <p className="att-muted">
              {me.shift ? <>Turno de hoy: {clockTime(me.shift.starts_at, zona)} a {clockTime(me.shift.ends_at, zona)}
                {me.shift_status ? ` · ${SHIFT_STATUS_LABELS[me.shift_status] ?? me.shift_status}` : ""}</>
                : "No tienes turno programado ahora."}
            </p>
          </>
        )}
        {me.shift_project && <p className="att-muted">Obra del turno: <strong>{me.shift_project.title}</strong></p>}
      </section>

      {!abierta && (
        <button type="button" className="att-btn is-primary is-big is-block" disabled={busy === "clock_in"}
          onClick={() => void run("clock_in", { project_id: me.shift_project?.id ?? null })}>
          {busy === "clock_in" ? "Tomando ubicación…" : "INICIAR TURNO"}
        </button>
      )}

      {abierta && entry && (
        <>
          <section className="att-card" aria-labelledby="att-desplazamientos">
            <h2 id="att-desplazamientos">Desplazamientos</h2>
            {me.projects_today.length ? (
              <>
                <label className="att-field">Obra
                  <select value={obra} onChange={(e) => setObra(e.target.value)}>
                    {me.projects_today.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
                  </select>
                </label>
                <div className="att-grid-3">
                  <button type="button" className="att-btn is-big" disabled={!!busy}
                    onClick={() => void run("en_route", { project_id: obra })}>En camino</button>
                  <button type="button" className="att-btn is-big" disabled={!!busy}
                    onClick={() => void run("arrived", { project_id: obra })}>Llegué</button>
                  <button type="button" className="att-btn is-big" disabled={!!busy}
                    onClick={() => void run("left_site", { project_id: obra })}>Salida de obra</button>
                </div>
              </>
            ) : <p className="att-muted">No tienes obras abiertas asignadas.</p>}
          </section>

          <section className="att-card" aria-labelledby="att-pausas">
            <h2 id="att-pausas">Pausas</h2>
            {entry.paused ? (
              <button type="button" className="att-btn is-big is-block" disabled={!!busy}
                onClick={() => void run("pause_end")}>Reanudar</button>
            ) : (
              <div className="att-form-row">
                <label className="att-field">Motivo
                  <select value={motivoPausa} onChange={(e) => setMotivoPausa(e.target.value)}>
                    <option value="">Almuerzo o descanso</option>
                    <option value="Compra de material">Compra de material</option>
                    <option value="Diligencia personal">Diligencia personal</option>
                    <option value="Otro">Otro</option>
                  </select>
                </label>
                <button type="button" className="att-btn is-big" disabled={!!busy}
                  onClick={() => void run("pause_start", { note: motivoPausa || "Almuerzo o descanso" })}>Pausa</button>
              </div>
            )}
          </section>

          <button type="button" className="att-btn is-danger is-big is-block" onClick={() => void abrirResumen()}>
            FINALIZAR TURNO
          </button>
        </>
      )}

      <section className="att-card" aria-labelledby="att-novedad">
        <div className="att-card-head">
          <h2 id="att-novedad">Novedades</h2>
          {!novedad && <button type="button" className="att-btn" onClick={() => setNovedad(true)}>Registrar novedad</button>}
        </div>
        {novedad ? <NoveltyForm entryId={entry?.id} onCancel={() => setNovedad(false)} onDone={() => setNovedad(false)} />
          : <p className="att-muted">¿Llegaste tarde, olvidaste marcar o no tuviste señal? Regístralo aquí y
            Administración lo revisa.</p>}
      </section>

      <section className="att-card" aria-labelledby="att-proximos">
        <h2 id="att-proximos">Próximos turnos</h2>
        {(turnos ?? []).length ? (
          <ul className="att-list">
            {(turnos ?? []).map((t) => (
              <li key={t.id}><strong>{new Date(t.starts_at).toLocaleDateString("es-US", { weekday: "short", day: "numeric",
                month: "short", timeZone: zona })}</strong> {clockTime(t.starts_at, zona)} a {clockTime(t.ends_at, zona)}
                {t.project_title ? ` · ${t.project_title}` : ""}</li>
            ))}
          </ul>
        ) : <p className="att-muted">Sin turnos programados esta semana.</p>}
      </section>

      <section className="att-card" aria-labelledby="att-historial">
        <h2 id="att-historial">Mis últimas jornadas</h2>
        {(entradas ?? []).length ? (
          <ul className="att-list">
            {(entradas ?? []).map((e) => (
              <li key={e.id}><strong>{e.work_date}</strong> {clockTime(e.clock_in_at, zona)} a {clockTime(e.clock_out_at, zona)}
                {" · "}{hm(e.effective_minutes)}{" · "}
                <span className={`att-pill is-${e.status}`}>{e.status === "approved" ? "Aprobada"
                  : e.status === "closed" ? "Por aprobar" : "Abierta"}</span></li>
            ))}
          </ul>
        ) : <p className="att-muted">Todavía no hay jornadas.</p>}
      </section>

      {resumen && (
        <div className="att-gate" role="dialog" aria-modal="true" aria-labelledby="att-resumen-titulo">
          <div className="att-gate-card">
            <h2 id="att-resumen-titulo">Resumen del turno</h2>
            <dl className="att-gate-facts">
              <div><dt>Ingreso</dt><dd>{clockTime(resumen.clock_in_at, zona)}</dd></div>
              <div><dt>Salida</dt><dd>{clockTime(resumen.clock_out_at, zona)}</dd></div>
              <div><dt>Transcurrido</dt><dd>{hm(resumen.elapsed_minutes)}</dd></div>
              <div><dt>Pausas</dt><dd>{resumen.pauses} · {hm(resumen.pause_minutes)}</dd></div>
              <div><dt>Horas efectivas</dt><dd><strong>{hm(resumen.effective_minutes)}</strong></dd></div>
              <div><dt>Turno programado</dt><dd>{resumen.shift ? `${clockTime(resumen.shift.starts_at, zona)} a ${
                clockTime(resumen.shift.ends_at, zona)} · ${hm(resumen.scheduled_minutes)}` : "Sin turno"}</dd></div>
              {resumen.difference_minutes != null && (
                <div><dt>Diferencia con la malla</dt><dd>{hm(resumen.difference_minutes)}</dd></div>)}
              <div><dt>Obras atendidas</dt><dd>{resumen.projects.length
                ? resumen.projects.map((p) => p.title).join(", ") : "Ninguna marcada con «Llegué»"}</dd></div>
            </dl>
            {resumen.early_leave_minutes > 0 && (
              <p className="att-banner is-warn">Sales {resumen.early_leave_minutes} min antes del fin del turno.
                Si hay un motivo, registra una novedad.</p>
            )}
            <label className="att-field">Observaciones o novedades
              <textarea value={nota} maxLength={2000} onChange={(e) => setNota(e.target.value)} />
            </label>
            <div className="att-actions">
              <button type="button" className="att-btn" onClick={() => setResumen(null)}>Volver</button>
              <button type="button" className="att-btn is-danger" disabled={busy === "clock_out"}
                onClick={async () => {
                  await run("clock_out", { note: nota || null });
                  setResumen(null);
                  setNota("");
                  qc.invalidateQueries({ queryKey: ["my-entries"] });
                  qc.invalidateQueries({ queryKey: ME_KEY });
                }}>
                {busy === "clock_out" ? "Finalizando…" : "Confirmar y finalizar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
