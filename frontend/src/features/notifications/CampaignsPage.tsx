import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "./notifications.css";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { listPrograms, programKeys } from "@/features/programs/api";
import { PaginationControls } from "@/components/PaginationControls";
import {
  addOptOut,
  campaignKeys,
  cancelCampaign,
  deleteOwnContact,
  getAudience,
  getCampaign,
  grantConsent,
  importOwnContacts,
  launchCampaign,
  listCampaigns,
  listOptOuts,
  listOwnContacts,
  listProducts,
  listRecipients,
  saveCampaign,
  saveProduct,
  testCampaign,
  timeAgo,
  type Audience,
  type Campaign,
  type CampaignChannel,
  type ConsentState,
  type Product,
} from "./api";

/** Filas por página en destinatarios, contactos y bajas (los tres pueden ser miles). */
const PAGE_SIZE = 50;

type Tab = "campaigns" | "contacts" | "products" | "optouts";
const ESTADO: Record<Campaign["status"], [string, string]> = {
  draft: ["Borrador", "is-draft"], scheduled: ["Programada", "is-submitted"], sending: ["Enviando", "is-submitted"],
  sent: ["Terminada", "is-paid"], cancelled: ["Cancelada", "is-void"],
};
const PERMISO: Record<ConsentState, [string, string]> = {
  granted: ["Con permiso", "is-paid"], none: ["Sin permiso", "is-preparing"], revoked: ["De baja", "is-rejected"],
  no_phone: ["—", "is-void"], no_email: ["—", "is-void"],
};
const CANAL: Record<CampaignChannel, string> = { sms: "SMS", email: "Correo", both: "SMS y correo" };
const tel = (t: string | null) => (t ? t.replace(/(\d{3})(\d{3})(\d{4})/, "($1) $2-$3") : "—");

/**
 * Campañas de productos por SMS y correo. El dueño escoge a quién escribir:
 * clientes del sistema y contactos propios que carga en "Contactos propios".
 * Solo salen a quienes tienen permiso de mercadeo registrado; cada SMS dice
 * cómo darse de baja (STOP) y cada correo lleva enlace de baja y dirección postal.
 */
export function CampaignsPage() {
  const [tab, setTab] = useState<Tab>("campaigns");
  const [abierta, setAbierta] = useState<string | "new" | null>(null);
  return (
    <div className="billing-page notices-page campaigns-page">
      <header className="billing-head">
        <div>
          <h1>Campañas</h1>
          <p>Ofrece tus productos por SMS o correo a los clientes y contactos que tú elijas.</p>
        </div>
        {tab === "campaigns" && abierta === null && (
          <div className="acta-actions"><button type="button" className="acta-btn is-primary" onClick={() => setAbierta("new")}>Nueva campaña</button></div>
        )}
      </header>
      <div className="notices-tabs" role="tablist">
        {([["campaigns", "Campañas"], ["contacts", "Contactos propios"], ["products", "Productos"], ["optouts", "Bajas"]] as [Tab, string][]).map(([k, l]) => (
          <button key={k} role="tab" type="button" aria-selected={tab === k} className={tab === k ? "is-on" : ""}
            onClick={() => { setTab(k); setAbierta(null); }}>{l}</button>
        ))}
      </div>
      {tab === "campaigns" && (abierta === null ? <CampaignList onOpen={setAbierta} />
        : <CampaignEditor id={abierta === "new" ? null : abierta} onClose={() => setAbierta(null)} onCreated={setAbierta} />)}
      {tab === "contacts" && <OwnContacts />}
      {tab === "products" && <Products />}
      {tab === "optouts" && <OptOuts />}
    </div>
  );
}

function CampaignList({ onOpen }: { onOpen: (id: string) => void }) {
  const { data, isLoading } = useQuery({ queryKey: campaignKeys.list, queryFn: listCampaigns });
  if (isLoading) return <p className="acta-empty">Cargando…</p>;
  return (
    <article className="acta">
      {(data ?? []).length === 0 ? <p className="acta-empty">Todavía no hay campañas. Crea la primera con «Nueva campaña».</p> : (
        <ul className="campaigns-list">
          {data!.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => onOpen(c.id)}>
                <span><strong>{c.name}</strong><small>{CANAL[c.channel]} · {c.preview}</small></span>
                <span className="queue-counts">
                  <span className={`billing-chip ${ESTADO[c.status][1]}`}>{ESTADO[c.status][0]}</span>
                  {c.status !== "draft" && <small>{c.stats.sent} enviados · {c.stats.pending} en cola</small>}
                  <span aria-hidden="true">›</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function CampaignEditor({ id, onClose, onCreated }: { id: string | null; onClose: () => void; onCreated: (id: string) => void }) {
  const qc = useQueryClient();
  const { data: c } = useQuery({ queryKey: campaignKeys.one(id ?? ""), queryFn: () => getCampaign(id!), enabled: !!id });
  const { data: productos } = useQuery({ queryKey: campaignKeys.products, queryFn: listProducts });
  const [nombre, setNombre] = useState("");
  const [producto, setProducto] = useState("");
  const [canal, setCanal] = useState<CampaignChannel>("sms");
  const [asunto, setAsunto] = useState("");
  const [mensaje, setMensaje] = useState("Hola {{nombre}}, ");
  const [publico, setPublico] = useState<Audience>({});
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  useEffect(() => {
    if (c) { setNombre(c.name); setProducto(c.product_id ?? ""); setCanal(c.channel); setAsunto(c.subject ?? ""); setMensaje(c.message); setPublico(c.audience ?? {}); }
  }, [c]);
  const borrador = !c || c.status === "draft";
  const prod = productos?.find((p) => p.id === producto);
  const llenar = (t: string) => t.replace(/\{\{\s*nombre\s*\}\}/g, "María").replace(/\{\{\s*producto\s*\}\}/g, prod?.name ?? "")
    .replace(/\{\{\s*precio\s*\}\}/g, prod?.price ?? "").trim();
  const vista = llenar(mensaje);
  const vistaSms = /stop/i.test(vista) ? vista : `${vista} Responde STOP para no recibir más.`;
  const conSms = canal !== "email";
  const conCorreo = canal !== "sms";
  const refrescar = () => { qc.invalidateQueries({ queryKey: campaignKeys.list }); if (id) qc.invalidateQueries({ queryKey: campaignKeys.one(id) }); };

  const guardar = useMutation({
    mutationFn: () => saveCampaign(id, { name: nombre, product_id: producto || null, channel: canal, subject: asunto || null, message: mensaje, audience: publico }),
    onSuccess: (r) => { setError(null); setAviso("Borrador guardado."); refrescar(); if (!id) onCreated(r.id); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  if (id && !c) return <p className="acta-empty">Cargando…</p>;
  return (
    <article className="acta">
      <button type="button" className="acta-back" onClick={onClose}><span aria-hidden="true">‹</span> Campañas</button>
      {c && !borrador ? <CampaignResult c={c} onChange={refrescar} /> : (
        <form className="campaign-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
          <div className="campaign-row">
            <div className="form-field">
              <label className="form-label" htmlFor="cp-name">Nombre de la campaña</label>
              <input id="cp-name" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej.: Mantenimiento de verano" required />
            </div>
            <div className="form-field">
              <label className="form-label" htmlFor="cp-prod">Producto (opcional)</label>
              <select id="cp-prod" value={producto} onChange={(e) => setProducto(e.target.value)}>
                <option value="">Sin producto</option>
                {(productos ?? []).filter((p) => p.active).map((p) => <option key={p.id} value={p.id}>{p.name}{p.price ? ` · ${p.price}` : ""}</option>)}
              </select>
            </div>
          </div>
          <div className="form-field">
            <span className="form-label">Enviar por</span>
            <div className="notices-channels" role="radiogroup" aria-label="Canal">
              {(["sms", "email", "both"] as CampaignChannel[]).map((k) => (
                <button key={k} type="button" role="radio" aria-checked={canal === k} className={canal === k ? "is-on" : ""} onClick={() => setCanal(k)}>{CANAL[k]}</button>
              ))}
            </div>
          </div>
          {conCorreo && (
            <div className="form-field">
              <label className="form-label" htmlFor="cp-subj">Asunto del correo</label>
              <input id="cp-subj" value={asunto} onChange={(e) => setAsunto(e.target.value)} maxLength={255} placeholder="Ej.: {{nombre}}, tu A/C listo para el verano" />
            </div>
          )}
          <div className="form-field">
            <label className="form-label" htmlFor="cp-msg">Mensaje</label>
            <textarea id="cp-msg" rows={conCorreo ? 6 : 4} maxLength={conSms ? 480 : 5000} value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
            <small className="notices-hint">Variables: {"{{nombre}} {{producto}} {{precio}}"}
              {conSms && ` · SMS: ${vistaSms.length} caracteres (${Math.ceil(vistaSms.length / 160)} SMS por persona)`}</small>
          </div>
          <div className="campaign-previews">
            {conSms && <div className="campaign-preview" aria-label="Vista previa SMS"><small>Así llega el SMS</small><p>{vistaSms}</p></div>}
            {conCorreo && (
              <div className="campaign-preview is-email" aria-label="Vista previa correo">
                <small>Así llega el correo</small>
                <strong>{llenar(asunto) || "(sin asunto)"}</strong>
                <p>{vista}</p>
                <small>Al pie: dirección de la empresa y enlace «Darme de baja».</small>
              </div>
            )}
          </div>
          <AudiencePicker value={publico} onChange={setPublico} canal={canal} />
          {error && <p className="form-error" role="alert">{error}</p>}
          {aviso && <p className="info-banner" role="status">{aviso}</p>}
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-line" disabled={!nombre.trim() || !mensaje.trim() || guardar.isPending}>Guardar borrador</button>
          </div>
          {id && <Launch id={id} canal={canal} beforeLaunch={() => guardar.mutateAsync()} onDone={refrescar} />}
        </form>
      )}
    </article>
  );
}

function AudiencePicker({ value, onChange, canal }: { value: Audience; onChange: (a: Audience) => void; canal: CampaignChannel }) {
  const qc = useQueryClient();
  const { data: programas } = useQuery({ queryKey: programKeys.list, queryFn: listPrograms });
  const filtros = { search: value.search, program_ids: value.program_ids, states: value.states, include_contacts: value.include_contacts ?? true };
  const { data } = useQuery({ queryKey: ["audience", filtros], queryFn: () => getAudience(filtros) });
  const elegidos = useMemo(() => new Set(value.selected ?? []), [value.selected]);
  const manual = elegidos.size > 0;
  const [fuente, setFuente] = useState("");
  const [confirmo, setConfirmo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const contactos = data?.contacts ?? [];
  const enPublico = manual ? contactos.filter((x) => elegidos.has(x.key)) : contactos;
  const conSms = canal !== "email";
  const conCorreo = canal !== "sms";
  const reciben = enPublico.filter((x) => (conSms && x.consent === "granted") || (conCorreo && x.email_consent === "granted")).length;
  const sinPermiso = enPublico.filter((x) => (conSms && x.consent === "none") || (conCorreo && x.email_consent === "none"));
  const permitir = useMutation({
    mutationFn: () => grantConsent(sinPermiso.map((x) => x.key), fuente, canal),
    onSuccess: () => { setFuente(""); setConfirmo(false); setError(null); qc.invalidateQueries({ queryKey: ["audience"] }); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const alternar = (k: string) => {
    const n = new Set(elegidos);
    if (n.has(k)) n.delete(k); else n.add(k);
    onChange({ ...value, selected: [...n] });
  };
  return (
    <fieldset className="campaign-audience">
      <legend>¿A quién?</legend>
      <div className="campaign-filters">
        <input aria-label="Buscar" placeholder="Buscar nombre, teléfono, correo o ciudad" value={value.search ?? ""}
          onChange={(e) => onChange({ ...value, search: e.target.value || undefined })} />
        <select aria-label="Programa" value={value.program_ids?.[0] ?? ""} onChange={(e) => onChange({ ...value, program_ids: e.target.value ? [e.target.value] : [] })}>
          <option value="">Todos los programas</option>
          {(programas ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select aria-label="Estado" value={value.states?.[0] ?? ""} onChange={(e) => onChange({ ...value, states: e.target.value ? [e.target.value] : [] })}>
          <option value="">CA, AZ y NV</option><option value="CA">California</option><option value="AZ">Arizona</option><option value="NV">Nevada</option>
        </select>
        <label className="billing-check"><input type="checkbox" checked={value.include_contacts ?? true}
          onChange={(e) => onChange({ ...value, include_contacts: e.target.checked })} /> Incluir contactos propios</label>
      </div>
      <p className="notices-hint">
        {manual ? `${elegidos.size} elegidos a mano` : `Todos los que cumplen el filtro (${contactos.length})`} · {reciben} reciben el mensaje.
        {manual && <> <button type="button" className="acta-link" onClick={() => onChange({ ...value, selected: [] })}>Quitar selección</button></>}
        {" "}Los filtros de programa y estado dejan fuera a los contactos propios.
      </p>
      <div className="tablewrap campaign-contacts"><table>
        <thead><tr><th aria-label="Elegir" /><th>Nombre</th>{conSms && <th>Teléfono</th>}{conCorreo && <th>Correo</th>}</tr></thead>
        <tbody>
          {contactos.slice(0, 500).map((x) => (
            <tr key={x.key}>
              <td><input type="checkbox" aria-label={`Elegir a ${x.name}`} checked={elegidos.has(x.key)} onChange={() => alternar(x.key)} /></td>
              <td><strong>{x.name}</strong><small>{x.kind === "contact" ? "Contacto propio" : [x.program ?? "Cliente", x.city, x.state].filter(Boolean).join(" · ")}</small></td>
              {conSms && <td><span className="mono">{tel(x.phone)}</span>{x.phone && <span className={`billing-chip ${PERMISO[x.consent][1]}`}>{PERMISO[x.consent][0]}</span>}</td>}
              {conCorreo && <td><span className="mono">{x.email ?? "—"}</span>{x.email && <span className={`billing-chip ${PERMISO[x.email_consent][1]}`}>{PERMISO[x.email_consent][0]}</span>}</td>}
            </tr>
          ))}
        </tbody>
      </table></div>
      {contactos.length === 0 && <p className="acta-empty">Nadie con teléfono o correo cumple el filtro. Puedes cargar contactos propios en la pestaña «Contactos propios».</p>}
      {sinPermiso.length > 0 && (
        <div className="campaign-consent">
          <strong>{sinPermiso.length} sin permiso de mercadeo: no recibirán el mensaje.</strong>
          <p>La ley de EE. UU. exige que la persona haya aceptado recibir promociones (TCPA para SMS, CAN-SPAM para correo). Si ya lo aceptaron, regístralo indicando cómo.</p>
          <div className="form-field">
            <label className="form-label" htmlFor="cs-src">¿Cómo dieron el permiso?</label>
            <input id="cs-src" value={fuente} onChange={(e) => setFuente(e.target.value)} placeholder="Ej.: firmaron la casilla de promociones en la visita" />
          </div>
          <label className="billing-check"><input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} /> Confirmo que estas {sinPermiso.length} personas aceptaron recibir promociones por {CANAL[canal].toLowerCase()}.</label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="acta-actions">
            <button type="button" className="acta-btn is-line" disabled={!confirmo || fuente.trim().length < 5 || permitir.isPending} onClick={() => permitir.mutate()}>Registrar permiso</button>
          </div>
        </div>
      )}
    </fieldset>
  );
}

function Launch({ id, canal, beforeLaunch, onDone }: { id: string; canal: CampaignChannel; beforeLaunch: () => Promise<unknown>; onDone: () => void }) {
  const [telefono, setTelefono] = useState("");
  const [cuando, setCuando] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const probar = useMutation({
    mutationFn: async (c: "sms" | "email") => { await beforeLaunch(); return testCampaign(id, c, telefono); },
    onSuccess: (r, c) => {
      setError(null);
      setMsg(r.result === "test" ? `Modo de prueba: el ${c === "sms" ? "SMS" : "correo"} no salió porque falta configurar el proveedor.`
        : c === "sms" ? "Prueba enviada a tu celular." : `Prueba enviada a ${r.to}.`);
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const lanzar = useMutation({
    mutationFn: async () => { await beforeLaunch(); return launchCampaign(id, cuando ? new Date(cuando).toISOString() : undefined); },
    onSuccess: (r) => { setError(null); setMsg(`En cola: ${r.summary.queued} envíos.`); onDone(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  return (
    <div className="campaign-launch">
      <h3 className="acta-section-title">Probar y lanzar</h3>
      <div className="campaign-filters">
        {canal !== "email" && <>
          <input aria-label="Tu celular para la prueba" type="tel" placeholder="Tu celular (el de Notificaciones → Cómo me avisan)" value={telefono} onChange={(e) => setTelefono(e.target.value)} />
          <button type="button" className="acta-btn is-quiet" disabled={telefono.length < 7 || probar.isPending} onClick={() => probar.mutate("sms")}>Probar SMS</button>
        </>}
        {canal !== "sms" && <button type="button" className="acta-btn is-quiet" disabled={probar.isPending} onClick={() => probar.mutate("email")}>Probar correo (a mi correo)</button>}
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="cp-when">Programar (opcional; vacío = ahora)</label>
        <input id="cp-when" type="datetime-local" value={cuando} onChange={(e) => setCuando(e.target.value)} />
      </div>
      <p className="notices-hint">Se guarda el borrador antes de probar y lanzar. Los SMS solo salen de 8 a. m. a 9 p. m. en la hora de cada cliente.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      {msg && <p className="info-banner" role="status">{msg}</p>}
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={lanzar.isPending}
          onClick={() => { if (window.confirm("¿Lanzar la campaña? Después ya no se edita.")) lanzar.mutate(); }}>Lanzar campaña</button>
      </div>
    </div>
  );
}

function CampaignResult({ c, onChange }: { c: Campaign; onChange: () => void }) {
  const [page, setPage] = useState(1);
  const { data } = useQuery({ queryKey: [...campaignKeys.recipients(c.id), page],
    queryFn: () => listRecipients(c.id, page, PAGE_SIZE),
    refetchInterval: c.status === "sending" || c.status === "scheduled" ? 15_000 : false });
  const cancelar = useMutation({ mutationFn: () => cancelCampaign(c.id), onSuccess: onChange });
  const s = c.audience.launch_summary;
  return (
    <div className="campaign-result">
      <div className="acta-title-row">
        <h2 className="acta-title">{c.name}</h2>
        <span className={`billing-chip ${ESTADO[c.status][1]}`}>{ESTADO[c.status][0]}</span>
      </div>
      <div className="campaign-preview">
        <small>{CANAL[c.channel]}</small>
        {c.channel !== "sms" && <strong>{c.preview_subject}</strong>}
        <p>{c.preview}</p>
      </div>
      <dl className="acta-meta">
        <div><dt>Enviados</dt><dd>{c.stats.sent}</dd></div>
        <div><dt>En cola</dt><dd>{c.stats.pending}</dd></div>
        <div><dt>Fallidos</dt><dd>{c.stats.failed}</dd></div>
        <div><dt>No enviados</dt><dd>{c.stats.skipped}</dd></div>
        {s && <div><dt>Excluidos sin permiso o de baja</dt><dd>{s.without_consent + s.opted_out}</dd></div>}
      </dl>
      {(c.status === "scheduled" || c.status === "sending") && (
        <div className="acta-actions"><button type="button" className="acta-btn is-quiet" onClick={() => { if (window.confirm("¿Cancelar lo que falta por enviar?")) cancelar.mutate(); }}>Cancelar campaña</button></div>
      )}
      <div className="tablewrap"><table className="notices-table">
        <thead><tr><th>Nombre</th><th>Canal</th><th>Para</th><th>Estado</th></tr></thead>
        <tbody>
          {(data?.items ?? []).map((r) => (
            <tr key={r.id}>
              <td>{r.name}</td><td>{r.channel === "sms" ? "SMS" : "Correo"}</td>
              <td className="mono">{r.channel === "sms" ? tel(r.address) : r.address}</td>
              <td>{{ pending: "En cola", sent: "Enviado", failed: "Falló", skipped: "No enviado" }[r.status] ?? r.status}
                {r.status === "pending" && r.next_attempt_at && <small>sale {new Date(r.next_attempt_at).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" })}</small>}
                {r.last_error && <small className="notices-error">{r.last_error}</small>}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}

function OwnContacts() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const { data } = useQuery({ queryKey: [...campaignKeys.contacts, page], queryFn: () => listOwnContacts(page, PAGE_SIZE) });
  const [texto, setTexto] = useState("");
  const [fuente, setFuente] = useState("");
  const [confirmo, setConfirmo] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refrescar = () => { qc.invalidateQueries({ queryKey: campaignKeys.contacts }); qc.invalidateQueries({ queryKey: ["audience"] }); };
  const cargar = useMutation({
    mutationFn: () => importOwnContacts(texto, fuente),
    onSuccess: (r) => {
      setError(null); setTexto(""); setConfirmo(false); refrescar();
      setMsg(`${r.created} nuevos, ${r.updated} actualizados.${r.already_opted_out ? ` ${r.already_opted_out} ya se habían dado de baja y siguen de baja.` : ""}${r.invalid.length ? ` ${r.invalid.length} líneas sin teléfono ni correo válido: ${r.invalid.slice(0, 3).join(" | ")}` : ""}`);
    },
    onError: (e) => { setMsg(null); setError(apiErrorMessage(e)); },
  });
  const borrar = useMutation({ mutationFn: deleteOwnContact, onSuccess: refrescar });
  const leerArchivo = async (f: File | undefined) => { if (f) setTexto(await f.text()); };
  return (
    <article className="acta">
      <p className="acta-lead">Números y correos que no están como clientes (tu lista propia). Pega una persona por línea —nombre, teléfono y/o correo, separados por coma— o sube un archivo CSV.</p>
      <form className="campaign-form" onSubmit={(e) => { e.preventDefault(); cargar.mutate(); }}>
        <div className="form-field">
          <label className="form-label" htmlFor="oc-text">Contactos</label>
          <textarea id="oc-text" rows={6} value={texto} onChange={(e) => setTexto(e.target.value)}
            placeholder={"Juan Pérez, (602) 555-0101, juan@correo.com\nMaría López, 7025550188\nana@correo.com"} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="oc-file">o sube un CSV</label>
          <input id="oc-file" type="file" accept=".csv,.txt,text/csv,text/plain" onChange={(e) => leerArchivo(e.target.files?.[0])} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="oc-src">¿Cómo dieron el permiso de recibir promociones?</label>
          <input id="oc-src" value={fuente} onChange={(e) => setFuente(e.target.value)} placeholder="Ej.: se inscribieron en la feria de Phoenix (formulario firmado)" />
        </div>
        <label className="billing-check"><input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} /> Confirmo que todas estas personas aceptaron recibir promociones por SMS y/o correo.</label>
        {error && <p className="form-error" role="alert">{error}</p>}
        {msg && <p className="info-banner" role="status">{msg}</p>}
        <div className="acta-actions">
          <button type="submit" className="acta-btn is-primary" disabled={!texto.trim() || !confirmo || fuente.trim().length < 5 || cargar.isPending}>
            {cargar.isPending ? "Cargando…" : "Cargar contactos"}</button>
        </div>
      </form>
      <h3 className="acta-section-title">Tu lista ({data?.total ?? 0})</h3>
      {(data?.items ?? []).length === 0 ? <p className="acta-empty">Todavía no hay contactos propios.</p> : (
        <div className="tablewrap campaign-contacts"><table>
          <thead><tr><th>Nombre</th><th>Teléfono</th><th>Correo</th><th aria-label="Acciones" /></tr></thead>
          <tbody>{data!.items.map((k) => (
            <tr key={k.id}><td>{k.name ?? "—"}</td><td className="mono">{tel(k.phone)}</td><td className="mono">{k.email ?? "—"}</td>
              <td><button type="button" className="acta-link" onClick={() => { if (window.confirm("¿Quitar este contacto de la lista?")) borrar.mutate(k.id); }}>Quitar</button></td></tr>
          ))}</tbody>
        </table></div>
      )}
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </article>
  );
}

function Products() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: campaignKeys.products, queryFn: listProducts });
  const [edit, setEdit] = useState<Partial<Product> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const guardar = useMutation({ mutationFn: () => saveProduct(edit as Product),
    onSuccess: () => { setEdit(null); setError(null); qc.invalidateQueries({ queryKey: campaignKeys.products }); },
    onError: (e) => setError(apiErrorMessage(e)) });
  return (
    <article className="acta">
      <div className="notices-toolbar">
        <p className="acta-lead">Lo que ofreces en tus campañas: equipos, mantenimiento o lo que quieras.</p>
        {!edit && <button type="button" className="acta-btn is-primary" onClick={() => setEdit({ name: "", active: true })}>Nuevo producto</button>}
      </div>
      {edit && (
        <form className="campaign-form campaign-product-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
          <div className="form-field"><label className="form-label" htmlFor="pd-n">Nombre</label>
            <input id="pd-n" value={edit.name ?? ""} onChange={(e) => setEdit({ ...edit, name: e.target.value })} required /></div>
          <div className="form-field"><label className="form-label" htmlFor="pd-p">Precio (texto libre)</label>
            <input id="pd-p" value={edit.price ?? ""} placeholder="Ej.: $89 o desde $1,200" onChange={(e) => setEdit({ ...edit, price: e.target.value || null })} /></div>
          <div className="form-field"><label className="form-label" htmlFor="pd-d">Descripción</label>
            <textarea id="pd-d" rows={2} value={edit.description ?? ""} onChange={(e) => setEdit({ ...edit, description: e.target.value || null })} /></div>
          <label className="billing-check"><input type="checkbox" checked={edit.active ?? true} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} /> Activo</label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={!edit.name?.trim() || guardar.isPending}>Guardar</button>
            <button type="button" className="acta-btn is-quiet" onClick={() => setEdit(null)}>Cancelar</button>
          </div>
        </form>
      )}
      {(data ?? []).length === 0 && !edit ? <p className="acta-empty">Sin productos todavía.</p> : (
        <ul className="sales-programs">
          {(data ?? []).map((p) => (
            <li key={p.id} className={p.active ? "" : "is-inactive"}>
              <button type="button" className="campaign-product" onClick={() => setEdit(p)}>
                <strong>{p.name}{p.price ? ` · ${p.price}` : ""}</strong>
                <span>{p.description ?? (p.active ? "" : "Inactivo")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function OptOuts() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const { data } = useQuery({ queryKey: [...campaignKeys.optOuts, page], queryFn: () => listOptOuts(page, PAGE_SIZE) });
  const [valor, setValor] = useState("");
  const [error, setError] = useState<string | null>(null);
  const agregar = useMutation({ mutationFn: () => addOptOut(valor, "Pidió no recibir más (registro manual)"),
    onSuccess: () => { setValor(""); setError(null); qc.invalidateQueries({ queryKey: campaignKeys.optOuts }); },
    onError: (e) => setError(apiErrorMessage(e)) });
  return (
    <article className="acta">
      <p className="acta-lead">Quien responde STOP o usa el enlace de baja del correo sale de todas las campañas al instante. Si alguien lo pide por otro medio, regístralo aquí.</p>
      <form className="campaign-filters" onSubmit={(e) => { e.preventDefault(); agregar.mutate(); }}>
        <input aria-label="Teléfono o correo" placeholder="Teléfono o correo" value={valor} onChange={(e) => setValor(e.target.value)} />
        <button type="submit" className="acta-btn is-line" disabled={valor.length < 5 || agregar.isPending}>Dar de baja</button>
      </form>
      {error && <p className="form-error" role="alert">{error}</p>}
      {(data?.items ?? []).length === 0 ? <p className="acta-empty">Nadie se ha dado de baja.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Canal</th><th>Teléfono o correo</th><th>Motivo</th><th>Cuándo</th></tr></thead>
          <tbody>{data!.items.map((o) => <tr key={`${o.channel}-${o.address}`}><td>{o.channel === "sms" ? "SMS" : "Correo"}</td>
            <td className="mono">{o.channel === "sms" ? tel(o.address) : o.address}</td><td>{o.reason}</td><td>{o.at ? timeAgo(o.at) : "—"}</td></tr>)}</tbody>
        </table></div>
      )}
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </article>
  );
}
