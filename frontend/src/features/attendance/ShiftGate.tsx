import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { clockTime, SHIFT_STATUS_LABELS } from "./api";
import { NoveltyForm } from "./NoveltyForm";
import { flush, LOCATION_REQUIRED, mark, setQueueUser } from "./offlineQueue";
import { LocationHelp } from "./LocationHelp";
import { useMark, useMyAttendance } from "./useAttendance";
import "./attendance.css";

let logoutHandler: ((logout: () => Promise<void> | void) => void) | null = null;

/**
 * Cerrar sesión con el turno abierto pide finalizarlo antes (spec, «Marcación
 * en el celular»). Cerrar sesión no cierra el turno.
 */
export function requestLogout(logout: () => Promise<void> | void) {
  if (logoutHandler) logoutHandler(logout);
  else void logout();
}

/** Minutos que la persona puede seguir sin marcar después de «registrar novedad». */
const SALTO_KEY = "crm.attendance.skip.";

/**
 * Va una sola vez en el layout. Hace tres cosas:
 *
 * 1. La ventana obligatoria: si hay un turno para marcar y no hay marcación,
 *    tapa la app hasta INICIAR TURNO, registrar una novedad o cerrar sesión.
 * 2. La cola sin señal: envía lo pendiente al abrir, al volver la red y cada
 *    30 s, y anota cuándo se pierde y se recupera la señal.
 * 3. El seguimiento cada N minutos con la app abierta, solo si la organización
 *    lo encendió (por defecto está apagado: solo eventos).
 */
export function ShiftGate() {
  const { user, hasPermission, logout } = useAuth();
  const puede = hasPermission("attendance.clock");
  const { data: me } = useMyAttendance();
  const { run, busy } = useMark();
  const navigate = useNavigate();
  const [novedad, setNovedad] = useState(false);
  const [sinPermiso, setSinPermiso] = useState(false);
  const [salto, setSalto] = useState<string | null>(null);
  const [salida, setSalida] = useState<null | (() => Promise<void> | void)>(null);
  const turnoAbierto = useRef(false);
  turnoAbierto.current = me?.entry?.status === "open";

  useEffect(() => {
    if (!puede || !user) return;
    setQueueUser(user.id);
    void flush();
    const enLinea = () => { void mark("connectivity_restored", { withLocation: false }); };
    const sinRed = () => { void mark("connectivity_lost", { withLocation: false }); };
    window.addEventListener("online", enLinea);
    window.addEventListener("offline", sinRed);
    const t = window.setInterval(() => { void flush(); }, 30_000);
    return () => {
      window.removeEventListener("online", enLinea);
      window.removeEventListener("offline", sinRed);
      window.clearInterval(t);
      setQueueUser(null);
    };
  }, [puede, user]);

  // Seguimiento con la app abierta (alternativa B), apagado por defecto.
  const intervalo = me?.tracking_interval_minutes ?? 0;
  const enTurno = me?.entry?.status === "open";
  useEffect(() => {
    if (!puede || !enTurno || intervalo <= 0) return;
    const t = window.setInterval(() => {
      if (document.visibilityState === "visible") void mark("tracking");
    }, intervalo * 60_000);
    return () => window.clearInterval(t);
  }, [puede, enTurno, intervalo]);

  useEffect(() => {
    logoutHandler = (logout) => {
      if (turnoAbierto.current) setSalida(() => logout);
      else void logout();
    };
    return () => { logoutHandler = null; };
  }, []);

  // Sin turno de la malla, el «no puedo iniciar» vale por ese día.
  const turnoId = me ? me.shift?.id ?? `sin-turno-${me.server_time.slice(0, 10)}` : null;
  useEffect(() => {
    if (!turnoId) return;
    try { setSalto(sessionStorage.getItem(SALTO_KEY + turnoId)); } catch { setSalto(null); }
  }, [turnoId]);

  const salir = async (logout: () => Promise<void> | void) => {
    setSalida(null);
    await mark("logout", { withLocation: false });
    await logout();
  };

  const avisoSalida = salida && (
    <div className="att-gate" role="dialog" aria-modal="true" aria-labelledby="att-salir-titulo">
      <div className="att-gate-card">
        <h2 id="att-salir-titulo">Tienes un turno abierto</h2>
        <p>Finalízalo antes de salir. Cerrar sesión no cierra el turno: seguirá contando hasta que lo finalices
          o Administración lo regularice.</p>
        <div className="att-actions is-stacked">
          <button type="button" className="att-btn is-primary is-big"
            onClick={() => { setSalida(null); navigate("/my-shift?finalizar=1"); }}>Finalizar turno</button>
          <button type="button" className="att-btn" onClick={() => void salir(salida)}>Salir sin finalizar</button>
          <button type="button" className="att-btn is-link" onClick={() => setSalida(null)}>Seguir en la app</button>
        </div>
      </div>
    </div>
  );

  if (!puede || !me?.must_clock_in || salto) return avisoSalida || null;

  const zona = me.timezone;
  const ahora = new Date(me.server_time);
  return (
    <>
      <div className="att-gate" role="dialog" aria-modal="true" aria-labelledby="att-gate-titulo">
        <div className="att-gate-card">
          <p className="att-eyebrow">Marcación de entrada</p>
          <h2 id="att-gate-titulo">{me.user.full_name}</h2>
          <p className="att-gate-date">
            {ahora.toLocaleDateString("es-US", { weekday: "long", day: "numeric", month: "long", timeZone: zona })}
            {" · "}<strong>{clockTime(me.server_time, zona)}</strong> <small>(hora del servidor)</small>
          </p>
          <dl className="att-gate-facts">
            <div><dt>Turno</dt><dd>{me.shift ? `${clockTime(me.shift.starts_at, zona)} a ${clockTime(me.shift.ends_at, zona)}` : "Sin turno programado hoy"}</dd></div>
            {me.shift_project && <div><dt>Obra</dt><dd>{me.shift_project.title}</dd></div>}
            <div><dt>Estado</dt><dd>
              {me.late_minutes > 0 ? `Tarde por ${me.late_minutes} min`
                : SHIFT_STATUS_LABELS[me.shift_status ?? ""] ?? "Pendiente"}</dd></div>
          </dl>
          <p className="att-gate-privacy">
            Se guarda tu ubicación al iniciar, al marcar en camino, llegué o salida de obra, en las pausas y al
            finalizar. La ven el Administrador y Administración, y se borra a los {me.location_retention_days} días.
            Tu navegador te pedirá permiso: sin él no se puede iniciar turno. Si no hay señal o GPS, inicia igual y queda «sin ubicación».
          </p>
          {sinPermiso && !novedad && <LocationHelp />}
          {novedad ? (
            <NoveltyForm defaultKind="late_arrival" onCancel={() => setNovedad(false)} onDone={() => {
              setNovedad(false);
              try { sessionStorage.setItem(SALTO_KEY + turnoId, "1"); } catch { /* sin almacenamiento */ }
              setSalto("1");
            }} />
          ) : (
            <div className="att-actions is-stacked">
              <button type="button" className="att-btn is-primary is-big" disabled={busy === "clock_in"}
                onClick={async () => {
                  const r = await run("clock_in", { project_id: me.shift_project?.id ?? null });
                  setSinPermiso(r.errors.some((e) => e.code === LOCATION_REQUIRED));
                }}>
                {busy === "clock_in" ? "Tomando ubicación…" : sinPermiso ? "YA LA ACTIVÉ: INICIAR TURNO" : "INICIAR TURNO"}
              </button>
              <button type="button" className="att-btn" onClick={() => setNovedad(true)}>
                No puedo iniciar: registrar novedad
              </button>
              <button type="button" className="att-btn is-link" onClick={() => void logout()}>
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </div>
      {avisoSalida}
    </>
  );
}

