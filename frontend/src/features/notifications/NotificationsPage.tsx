import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "./notifications.css";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { PaginationControls } from "@/components/PaginationControls";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import {
  getNoticeSettings,
  runAlertsNow,
  getPrefs,
  listNotices,
  listTemplates,
  markAllRead,
  markRead,
  noticeKeys,
  resendDelivery,
  type Delivery,
  resetTemplate,
  saveTemplate,
  setNoticeSettings,
  setPrefs,
  timeAgo,
  type TemplateRow,
} from "./api";

type Tab = "mine" | "prefs" | "deliveries" | "templates" | "settings";

/**
 * Notificaciones (módulo 7). Todos ven sus avisos y eligen si quieren correo
 * o SMS; quien tiene `notifications.manage` ve además el historial de envíos
 * con reenvío, edita las plantillas y ajusta las alertas.
 */
export function NotificationsPage() {
  const { hasPermission } = useAuth();
  const admin = hasPermission("notifications.manage");
  const [tab, setTab] = useState<Tab>("mine");
  const tabs: [Tab, string][] = [["mine", "Mis avisos"], ["prefs", "Cómo me avisan"],
    ...(admin ? ([["deliveries", "Envíos"], ["templates", "Plantillas"], ["settings", "Alertas"]] as [Tab, string][]) : [])];
  return (
    <div className="billing-page notices-page">
      <header className="billing-head">
        <div>
          <h1>Notificaciones</h1>
          <p>Lo que pasa con tus expedientes, instalaciones y cobros, sin tener que buscarlo.</p>
        </div>
      </header>
      <div className="notices-tabs" role="tablist">
        {tabs.map(([k, l]) => (
          <button key={k} role="tab" type="button" aria-selected={tab === k} className={tab === k ? "is-on" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "mine" && <MyNotices />}
      {tab === "prefs" && <Prefs />}
      {tab === "deliveries" && <Deliveries />}
      {tab === "templates" && <Templates />}
      {tab === "settings" && <Settings />}
    </div>
  );
}

function MyNotices() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [soloSinLeer, setSoloSinLeer] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: noticeKeys.list(soloSinLeer), queryFn: () => listNotices(soloSinLeer, 100) });
  const refrescar = () => { qc.invalidateQueries({ queryKey: ["notices"] }); qc.invalidateQueries({ queryKey: noticeKeys.count }); };
  const leer = useMutation({ mutationFn: markRead, onSuccess: refrescar });
  const leerTodo = useMutation({ mutationFn: markAllRead, onSuccess: refrescar });
  return (
    <article className="acta">
      <div className="notices-toolbar">
        <label className="billing-check"><input type="checkbox" checked={soloSinLeer} onChange={(e) => setSoloSinLeer(e.target.checked)} /> Solo sin leer</label>
        {(data?.unread ?? 0) > 0 && <button type="button" className="acta-btn is-quiet" onClick={() => leerTodo.mutate()}>Marcar todas como leídas</button>}
      </div>
      {isLoading ? <p className="acta-empty">Cargando…</p> : (data?.items ?? []).length === 0 ? (
        <p className="acta-empty">{soloSinLeer ? "Nada sin leer." : "Todavía no tienes avisos. Aparecen cuando algo de tu trabajo cambia."}</p>
      ) : (
        <ul className="notice-list">
          {data!.items.map((n) => (
            <li key={n.id} className={n.read ? "" : "is-unread"}>
              <button type="button" onClick={() => { if (!n.read) leer.mutate(n.id); if (n.link) navigate(n.link); }}>
                <strong>{n.title}</strong>
                <span>{n.body}</span>
                <small>{timeAgo(n.created_at)}{n.link ? " · abrir ›" : ""}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function Prefs() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: noticeKeys.prefs, queryFn: getPrefs });
  const [email, setEmail] = useState(true);
  const [sms, setSms] = useState(false);
  const [tel, setTel] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (data) { setEmail(data.email_enabled); setSms(data.sms_enabled); setTel(data.sms_phone ?? ""); } }, [data]);
  const guardar = useMutation({
    mutationFn: () => setPrefs({ email_enabled: email, sms_enabled: sms, sms_phone: tel || null }),
    onSuccess: (p) => { qc.setQueryData(noticeKeys.prefs, p); setError(null); setMsg("Guardado."); },
    onError: (e) => { setMsg(null); setError(apiErrorMessage(e)); },
  });
  return (
    <article className="acta notices-prefs">
      <p className="acta-lead">Siempre ves tus avisos aquí y en la campana. Además puedes recibirlos por:</p>
      <form onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
        <label className="notices-switch">
          <input type="checkbox" checked={email} onChange={(e) => setEmail(e.target.checked)} />
          <span><strong>Correo</strong><small>a {data?.email ?? "tu correo"}</small></span>
        </label>
        <label className="notices-switch">
          <input type="checkbox" checked={sms} onChange={(e) => setSms(e.target.checked)} />
          <span><strong>SMS</strong><small>mensaje corto al celular</small></span>
        </label>
        {sms && (
          <div className="form-field">
            <label className="form-label" htmlFor="sms-tel">Celular</label>
            <input id="sms-tel" type="tel" inputMode="tel" autoComplete="tel" value={tel} onChange={(e) => setTel(e.target.value)} placeholder="(818) 555-0101" />
          </div>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
        {msg && <p className="info-banner" role="status">{msg}</p>}
        <div className="acta-actions"><button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>Guardar</button></div>
      </form>
    </article>
  );
}

const ESTADO: Record<string, [string, string]> = {
  pending: ["En cola", "is-preparing"], sent: ["Enviado", "is-paid"], failed: ["Falló", "is-rejected"], skipped: ["No enviado", "is-void"],
};

function Deliveries() {
  const qc = useQueryClient();
  const [estado, setEstado] = useState("");
  const lista = usePaginatedQuery<Delivery>({ key: ["notice-deliveries"], path: "/notifications/deliveries", pageSize: 50,
    params: { status: estado || undefined } });
  const { items: data, isLoading } = lista;
  const [error, setError] = useState<string | null>(null);
  const reenviar = useMutation({
    mutationFn: resendDelivery, onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: ["notice-deliveries"] }); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  return (
    <article className="acta">
      <div className="notices-toolbar">
        <label className="form-label" htmlFor="dl-status">Estado</label>
        <select id="dl-status" value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="">Todos</option>
          {Object.entries(ESTADO).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {isLoading ? <p className="acta-empty">Cargando…</p> : data.length === 0 ? <p className="acta-empty">Sin envíos.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Aviso</th><th>Canal</th><th>Para</th><th>Estado</th><th>Cuándo</th><th /></tr></thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.id}>
                <td><strong>{d.notice_label}</strong><small>{d.title}</small></td>
                <td>{d.channel === "email" ? "Correo" : "SMS"}</td>
                <td className="mono">{d.to}</td>
                <td><span className={`billing-chip ${ESTADO[d.status][1]}`}>{ESTADO[d.status][0]}</span>
                  {d.last_error && <small className="notices-error">{d.last_error}</small>}
                  {d.attempts > 1 && <small>{d.attempts} intentos</small>}</td>
                <td>{timeAgo(d.sent_at ?? d.created_at)}</td>
                <td>{(d.status === "failed" || d.status === "skipped") && (
                  <button type="button" className="acta-link" disabled={reenviar.isPending} onClick={() => reenviar.mutate(d.id)}>Reenviar</button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      <PaginationControls {...lista.controls} />
    </article>
  );
}

const CANAL: Record<string, string> = { in_app: "En la app", email: "Correo", sms: "SMS" };

function Templates() {
  const { data, isLoading } = useQuery({ queryKey: noticeKeys.templates, queryFn: listTemplates });
  const [abierto, setAbierto] = useState<string | null>(null);
  if (isLoading) return <p className="acta-empty">Cargando…</p>;
  return (
    <article className="acta">
      <p className="acta-lead">Variables disponibles: <span className="mono">{"{{expediente}} {{cliente}} {{programa}} {{vendedor}} {{motivo}} {{proyecto}} {{fecha}} {{direccion}} {{monto}} {{dias}} {{permiso}}"}</span>. Las que no apliquen al aviso quedan vacías.</p>
      <ul className="notices-templates">
        {(data ?? []).map((t) => (
          <li key={t.code}>
            <button type="button" className="notices-template-head" aria-expanded={abierto === t.code} onClick={() => setAbierto(abierto === t.code ? null : t.code)}>
              <span><strong>{t.label}</strong><small>Para: {t.audience}</small></span>
              <span>{Object.values(t.channels).some((c) => c.customized) && <span className="billing-chip is-submitted">Editada</span>} {abierto === t.code ? "▴" : "▾"}</span>
            </button>
            {abierto === t.code && <TemplateEditor row={t} />}
          </li>
        ))}
      </ul>
    </article>
  );
}

function TemplateEditor({ row }: { row: TemplateRow }) {
  const qc = useQueryClient();
  const [canal, setCanal] = useState<"in_app" | "email" | "sms">("in_app");
  const actual = row.channels[canal];
  const [asunto, setAsunto] = useState(actual.subject);
  const [cuerpo, setCuerpo] = useState(actual.body);
  const [activa, setActiva] = useState(actual.active);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setAsunto(actual.subject); setCuerpo(actual.body); setActiva(actual.active); setError(null); }, [canal, actual]);
  const listo = () => qc.invalidateQueries({ queryKey: noticeKeys.templates });
  const guardar = useMutation({ mutationFn: () => saveTemplate(row.code, canal, { subject: asunto, body: cuerpo, active: activa }),
    onSuccess: listo, onError: (e) => setError(apiErrorMessage(e)) });
  const restaurar = useMutation({ mutationFn: () => resetTemplate(row.code, canal), onSuccess: listo });
  return (
    <form className="notices-template-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <div className="notices-channels" role="tablist">
        {(["in_app", "email", "sms"] as const).map((c) => (
          <button key={c} type="button" role="tab" aria-selected={canal === c} className={canal === c ? "is-on" : ""} onClick={() => setCanal(c)}>
            {CANAL[c]}{row.channels[c].customized ? " ·" : ""}
          </button>
        ))}
      </div>
      {canal !== "sms" && (
        <div className="form-field">
          <label className="form-label" htmlFor={`t-sub-${row.code}`}>{canal === "email" ? "Asunto" : "Título"}</label>
          <input id={`t-sub-${row.code}`} value={asunto} onChange={(e) => setAsunto(e.target.value)} maxLength={255} />
        </div>
      )}
      <div className="form-field">
        <label className="form-label" htmlFor={`t-body-${row.code}`}>{canal === "sms" ? "Mensaje (corto)" : "Texto"}</label>
        <textarea id={`t-body-${row.code}`} rows={canal === "sms" ? 2 : 3} value={cuerpo} onChange={(e) => setCuerpo(e.target.value)} maxLength={2000} />
        {canal === "sms" && <small className="notices-hint">{cuerpo.length} caracteres · un SMS son 160</small>}
      </div>
      {canal !== "in_app" && (
        <label className="billing-check"><input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} /> Enviar por {CANAL[canal].toLowerCase()}</label>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={!cuerpo.trim() || guardar.isPending}>Guardar</button>
        {actual.customized && <button type="button" className="acta-btn is-quiet" onClick={() => restaurar.mutate()}>Volver al texto original</button>}
      </div>
    </form>
  );
}

function Settings() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: noticeKeys.settings, queryFn: getNoticeSettings });
  const [dias, setDias] = useState(3);
  const [permiso, setPermiso] = useState(7);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (data) { setDias(data.approval_alert_business_days); setPermiso(data.permit_expiry_alert_days); } }, [data]);
  const guardar = useMutation({
    mutationFn: () => setNoticeSettings({ approval_alert_business_days: dias, permit_expiry_alert_days: permiso }),
    onSuccess: (s) => { qc.setQueryData(noticeKeys.settings, s); setError(null); setMsg("Guardado. Se aplica en la próxima revisión diaria o al tocar «Revisar ahora»."); },
    onError: (e) => { setMsg(null); setError(apiErrorMessage(e)); },
  });
  // Sin esperar a la revisión de las 14:00 UTC: útil al cambiar un umbral.
  const revisar = useMutation({
    mutationFn: runAlertsNow,
    onSuccess: ({ created }) => {
      setError(null);
      setMsg(created ? `Se ${created === 1 ? "creó 1 aviso" : `crearon ${created} avisos`}.` : "No había nada nuevo para avisar.");
      qc.invalidateQueries({ queryKey: noticeKeys.count });
      qc.invalidateQueries({ queryKey: ["notices"] });
    },
    onError: (e) => { setMsg(null); setError(apiErrorMessage(e)); },
  });
  return (
    <article className="acta notices-prefs">
      <form onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
        <div className="form-field">
          <label className="form-label" htmlFor="s-dias">Avisar si un expediente lleva más de estos días hábiles en «Pendiente de aprobación»</label>
          <input id="s-dias" type="number" min={1} max={30} value={dias} onChange={(e) => setDias(Number(e.target.value))} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="s-perm">Avisar cuando un permiso venza en estos días o menos</label>
          <input id="s-perm" type="number" min={1} max={90} value={permiso} onChange={(e) => setPermiso(Number(e.target.value))} />
        </div>
        <dl className="acta-meta notices-providers">
          <div><dt>Correo</dt><dd>{data?.email_provider === "smtp" ? "SMTP activo" : "Modo de prueba (no envía)"}</dd></div>
          <div><dt>SMS</dt><dd>{data?.sms_provider === "masiv" ? "Masiv activo" : "Modo de prueba (no envía)"}</dd></div>
          <div><dt>SMS al cliente</dt><dd>Apagado hasta registrar su consentimiento</dd></div>
        </dl>
        {error && <p className="form-error" role="alert">{error}</p>}
        {msg && <p className="info-banner" role="status">{msg}</p>}
        <div className="acta-actions">
          <button type="button" className="acta-btn is-quiet" disabled={revisar.isPending} onClick={() => revisar.mutate()}>
            {revisar.isPending ? "Revisando…" : "Revisar ahora"}</button>
          <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>Guardar</button>
        </div>
      </form>
    </article>
  );
}
