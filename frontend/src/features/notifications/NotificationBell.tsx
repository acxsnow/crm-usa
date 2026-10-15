import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "./notifications.css";
import { useAuth } from "@/features/auth/AuthContext";
import { listNotices, markAllRead, markRead, noticeKeys, timeAgo, unreadCount, type Notice } from "./api";

/**
 * Campana del encabezado (módulo 7): cuántos avisos sin leer y los últimos.
 * Consulta cada minuto, y solo con la pestaña visible: en campo la señal es
 * débil y el teléfono no debe gastar datos en segundo plano.
 */
export function NotificationBell() {
  const { hasPermission } = useAuth();
  const puede = hasPermission("notifications.read_own") || hasPermission("notifications.manage");
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  const { data: sinLeer = 0 } = useQuery({
    queryKey: noticeKeys.count, queryFn: unreadCount, enabled: puede,
    refetchInterval: 60_000, refetchIntervalInBackground: false,
  });
  const { data: lista } = useQuery({ queryKey: noticeKeys.list(false), queryFn: () => listNotices(false, 8), enabled: puede && abierto });
  const refrescar = () => { qc.invalidateQueries({ queryKey: noticeKeys.count }); qc.invalidateQueries({ queryKey: ["notices"] }); };
  const leer = useMutation({ mutationFn: markRead, onSuccess: refrescar });
  const leerTodo = useMutation({ mutationFn: markAllRead, onSuccess: refrescar });

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setAbierto(false); };
    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fuera); document.removeEventListener("keydown", esc); };
  }, [abierto]);

  if (!puede) return null;
  const abrir = (n: Notice) => {
    if (!n.read) leer.mutate(n.id);
    setAbierto(false);
    if (n.link) navigate(n.link);
  };
  return (
    <div className="notice-bell" ref={caja}>
      <button type="button" className="notification-button" aria-haspopup="true" aria-expanded={abierto}
        aria-label={sinLeer ? `Notificaciones, ${sinLeer} sin leer` : "Notificaciones"} onClick={() => setAbierto((v) => !v)}>
        {/* Campana dibujada (antes un rombo ♢ que no se leía como avisos). */}
        <svg className="notice-bell-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
          strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {sinLeer > 0 && <span className="notice-badge">{sinLeer > 99 ? "99+" : sinLeer}</span>}
      </button>
      {abierto && (
        <div className="notice-panel" role="dialog" aria-label="Notificaciones">
          <div className="notice-panel-head">
            <strong>Notificaciones</strong>
            {sinLeer > 0 && <button type="button" className="acta-link" onClick={() => leerTodo.mutate()}>Marcar todas como leídas</button>}
          </div>
          {!lista ? <p className="acta-empty">Cargando…</p> : lista.items.length === 0 ? (
            <p className="acta-empty">No tienes avisos todavía.</p>
          ) : (
            <ul className="notice-list is-compact">
              {lista.items.map((n) => (
                <li key={n.id} className={n.read ? "" : "is-unread"}>
                  <button type="button" onClick={() => abrir(n)}>
                    <strong>{n.title}</strong>
                    <span>{n.body}</span>
                    <small>{timeAgo(n.created_at)}</small>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Link to="/notifications" className="notice-panel-all" onClick={() => setAbierto(false)}>Ver todas y ajustes</Link>
        </div>
      )}
    </div>
  );
}
