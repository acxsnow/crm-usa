import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "./notifications.css";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { listPrograms, programKeys } from "@/features/programs/api";
import {
  addOptOut,
  campaignKeys,
  cancelCampaign,
  getCampaign,
  getAudience,
  grantConsent,
  launchCampaign,
  listCampaigns,
  listOptOuts,
  listProducts,
  listRecipients,
  saveCampaign,
  saveProduct,
  testCampaign,
  timeAgo,
  type Audience,
  type Campaign,
  type Product,
} from "./api";

type Tab = "campaigns" | "products" | "optouts";
const ESTADO: Record<Campaign["status"], [string, string]> = {
  draft: ["Borrador", "is-draft"], scheduled: ["Programada", "is-submitted"], sending: ["Enviando", "is-submitted"],
  sent: ["Terminada", "is-paid"], cancelled: ["Cancelada", "is-void"],
};
const PERMISO: Record<string, [string, string]> = {
  granted: ["Con permiso", "is-paid"], none: ["Sin permiso", "is-preparing"], revoked: ["Se dio de baja", "is-rejected"],
};

/**
 * Campañas de SMS de productos. El dueño escoge a quién escribir entre los
 * clientes con teléfono; solo salen los que tienen permiso de mercadeo
 * registrado (ley TCPA), cada mensaje lleva cómo darse de baja y se envía de
 * 8 a. m. a 9 p. m. en la hora del cliente.
 */
export function CampaignsPage() {
  const [tab, setTab] = useState<Tab>("campaigns");
  const [abierta, setAbierta] = useState<string | "new" | null>(null);
  return (
    <div className="billing-page notices-page campaigns-page">
      <header className="billing-head">
        <div>
          <h1>Campañas SMS</h1>
          <p>Ofrece tus productos por mensaje de texto a los clientes que tú elijas.</p>
        </div>
        {tab === "campaigns" && abierta === null && (
          <div className="acta-actions"><button type="button" className="acta-btn is-primary" onClick={() => setAbierta("new")}>Nueva campaña</button></div>
        )}
      </header>
      <div className="notices-tabs" role="tablist">
        {([["campaigns", "Campañas"], ["products", "Productos"], ["optouts", "Bajas (STOP)"]] as [Tab, string][]).map(([k, l]) => (
          <button key={k} role="tab" type="button" aria-selected={tab === k} className={tab === k ? "is-on" : ""}
            onClick={() => { setTab(k); setAbierta(null); }}>{l}</button>
        ))}
      </div>
      {tab === "campaigns" && (abierta === null ? <CampaignList onOpen={setAbierta} /> : <CampaignEditor id={abierta === "new" ? null : abierta} onClose={() => setAbierta(null)} onCreated={setAbierta} />)}
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
        <ul className="sales-cases campaigns-list">
          {data!.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => onOpen(c.id)}>
                <span><strong>{c.name}</strong><small>{c.preview}</small></span>
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
  const [mensaje, setMensaje] = useState("Hola {{nombre}}, ");
  const [publico, setPublico] = useState<Audience>({});
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  useEffect(() => {
    if (c) { setNombre(c.name); setProducto(c.product_id ?? ""); setMensaje(c.message); setPublico(c.audience ?? {}); }
  }, [c]);
  const borrador = !c || c.status === "draft";
  const prod = productos?.find((p) => p.id === producto);
  const vista = (mensaje.replace(/\{\{\s*nombre\s*\}\}/g, "María").replace(/\{\{\s*producto\s*\}\}/g, prod?.name ?? "")
    .replace(/\{\{\s*precio\s*\}\}/g, prod?.price ?? "")).trim();
  const vistaFinal = /stop/i.test(vista) ? vista : `${vista} Responde STOP para no recibir más.`;
  const refrescar = () => { qc.invalidateQueries({ queryKey: campaignKeys.list }); if (id) qc.invalidateQueries({ queryKey: campaignKeys.one(id) }); };

  const guardar = useMutation({
    mutationFn: () => saveCampaign(id, { name: nombre, product_id: producto || null, message: mensaje, audience: publico }),
    onSuccess: (r) => { setError(null); setAviso("Borrador guardado."); refrescar(); if (!id) onCreated(r.id); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  if (id && !c) return <p className="acta-empty">Cargando…</p>;
  return (
    <div className="campaign-grid">
      <article className="acta">
        <button type="button" className="acta-back" onClick={onClose}><span aria-hidden="true">‹</span> Campañas</button>
        {c && !borrador ? <CampaignResult c={c} onChange={refrescar} /> : (
          <form className="campaign-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
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
            <div className="form-field">
              <label className="form-label" htmlFor="cp-msg">Mensaje</label>
              <textarea id="cp-msg" rows={4} maxLength={480} value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
              <small className="notices-hint">Variables: {"{{nombre}} {{producto}} {{precio}}"} · {vistaFinal.length} caracteres ({Math.ceil(vistaFinal.length / 160)} SMS por persona)</small>
            </div>
            <div className="campaign-preview" aria-label="Vista previa">
              <small>Así lo recibe</small>
              <p>{vistaFinal}</p>
            </div>
            <AudiencePicker value={publico} onChange={setPublico} />
            {error && <p className="form-error" role="alert">{error}</p>}
            {aviso && <p className="info-banner" role="status">{aviso}</p>}
            <div className="acta-actions">
              <button type="submit" className="acta-btn is-line" disabled={!nombre.trim() || !mensaje.trim() || guardar.isPending}>Guardar borrador</button>
            </div>
            {id && <Launch id={id} beforeLaunch={() => guardar.mutateAsync()} onDone={refrescar} />}
          </form>
        )}
      </article>
    </div>
  );
}

function AudiencePicker({ value, onChange }: { value: Audience; onChange: (a: Audience) => void }) {
  const qc = useQueryClient();
  const { data: programas } = useQuery({ queryKey: programKeys.list, queryFn: listPrograms });
  const filtros = { search: value.search, program_ids: value.program_ids, states: value.states };
  const { data } = useQuery({ queryKey: ["audience", filtros], queryFn: () => getAudience(filtros) });
  const elegidos = useMemo(() => new Set(value.customer_ids ?? []), [value.customer_ids]);
  const manual = elegidos.size > 0;
  const [fuente, setFuente] = useState("");
  const [confirmo, setConfirmo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const contactos = data?.contacts ?? [];
  const enPublico = manual ? contactos.filter((x) => elegidos.has(x.customer_id)) : contactos;
  const sinPermiso = enPublico.filter((x) => x.consent === "none");
  const permitir = useMutation({
    mutationFn: () => grantConsent(sinPermiso.map((x) => x.customer_id), fuente),
    onSuccess: () => { setFuente(""); setConfirmo(false); setError(null); qc.invalidateQueries({ queryKey: ["audience"] }); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const alternar = (cid: string) => {
    const n = new Set(elegidos);
    if (n.has(cid)) n.delete(cid); else n.add(cid);
    onChange({ ...value, customer_ids: [...n] });
  };
  return (
    <fieldset className="campaign-audience">
      <legend>¿A quién?</legend>
      <div className="campaign-filters">
        <input aria-label="Buscar" placeholder="Buscar nombre, teléfono o ciudad" value={value.search ?? ""}
          onChange={(e) => onChange({ ...value, search: e.target.value || undefined })} />
        <select aria-label="Programa" value={value.program_ids?.[0] ?? ""} onChange={(e) => onChange({ ...value, program_ids: e.target.value ? [e.target.value] : [] })}>
          <option value="">Todos los programas</option>
          {(programas ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select aria-label="Estado" value={value.states?.[0] ?? ""} onChange={(e) => onChange({ ...value, states: e.target.value ? [e.target.value] : [] })}>
          <option value="">CA, AZ y NV</option><option value="CA">California</option><option value="AZ">Arizona</option><option value="NV">Nevada</option>
        </select>
      </div>
      <p className="notices-hint">
        {manual ? `${elegidos.size} elegidos a mano` : `Todos los que cumplen el filtro (${contactos.length})`} ·
        {" "}{enPublico.filter((x) => x.consent === "granted").length} con permiso reciben el mensaje.
        {manual && <> {" "}<button type="button" className="acta-link" onClick={() => onChange({ ...value, customer_ids: [] })}>Quitar selección</button></>}
      </p>
      <div className="tablewrap campaign-contacts"><table>
        <thead><tr><th aria-label="Elegir" /><th>Cliente</th><th>Teléfono</th><th>Lugar</th><th>Permiso</th></tr></thead>
        <tbody>
          {contactos.slice(0, 300).map((x) => (
            <tr key={x.customer_id}>
              <td><input type="checkbox" aria-label={`Elegir a ${x.name}`} checked={elegidos.has(x.customer_id)} onChange={() => alternar(x.customer_id)} /></td>
              <td><strong>{x.name}</strong><small>{x.program ?? "sin programa"}</small></td>
              <td className="mono">{x.phone.replace(/(\d{3})(\d{3})(\d{4})/, "($1) $2-$3")}</td>
              <td>{[x.city, x.state].filter(Boolean).join(", ") || "—"}</td>
              <td><span className={`billing-chip ${PERMISO[x.consent][1]}`}>{PERMISO[x.consent][0]}</span></td>
            </tr>
          ))}
        </tbody>
      </table></div>
      {contactos.length === 0 && <p className="acta-empty">Ningún cliente con teléfono cumple el filtro.</p>}
      {sinPermiso.length > 0 && (
        <div className="campaign-consent">
          <strong>{sinPermiso.length} sin permiso de mercadeo: no recibirán el mensaje.</strong>
          <p>La ley de EE. UU. (TCPA) exige que la persona haya aceptado recibir promociones por SMS. Si ya lo aceptaron, regístralo indicando cómo.</p>
          <div className="form-field">
            <label className="form-label" htmlFor="cs-src">¿Cómo dieron el permiso?</label>
            <input id="cs-src" value={fuente} onChange={(e) => setFuente(e.target.value)} placeholder="Ej.: firmaron la casilla de promociones en la visita" />
          </div>
          <label className="billing-check"><input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} /> Confirmo que estas {sinPermiso.length} personas aceptaron recibir promociones por SMS.</label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="acta-actions">
            <button type="button" className="acta-btn is-line" disabled={!confirmo || fuente.trim().length < 5 || permitir.isPending} onClick={() => permitir.mutate()}>Registrar permiso</button>
          </div>
        </div>
      )}
    </fieldset>
  );
}

function Launch({ id, beforeLaunch, onDone }: { id: string; beforeLaunch: () => Promise<unknown>; onDone: () => void }) {
  const [tel, setTel] = useState("");
  const [cuando, setCuando] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const probar = useMutation({ mutationFn: () => testCampaign(id, tel),
    onSuccess: (r) => { setError(null); setMsg(r.result === "test" ? "Modo de prueba: Masiv no está configurado, no salió el SMS." : "Prueba enviada a tu celular."); },
    onError: (e) => setError(apiErrorMessage(e)) });
  const lanzar = useMutation({ mutationFn: async () => { await beforeLaunch(); return launchCampaign(id, cuando ? new Date(cuando).toISOString() : undefined); },
    onSuccess: (r) => { setError(null); setMsg(`En cola para ${r.summary.queued} personas.`); onDone(); },
    onError: (e) => setError(apiErrorMessage(e)) });
  return (
    <div className="campaign-launch">
      <h3 className="acta-section-title">Probar y lanzar</h3>
      <div className="campaign-filters">
        <input aria-label="Tu celular para la prueba" type="tel" placeholder="Tu celular para la prueba" value={tel} onChange={(e) => setTel(e.target.value)} />
        <button type="button" className="acta-btn is-quiet" disabled={tel.length < 7 || probar.isPending} onClick={() => probar.mutate()}>Enviarme una prueba</button>
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="cp-when">Programar (opcional; vacío = ahora)</label>
        <input id="cp-when" type="datetime-local" value={cuando} onChange={(e) => setCuando(e.target.value)} />
      </div>
      <p className="notices-hint">Se guarda el borrador antes de lanzar. Solo sale de 8 a. m. a 9 p. m. en la hora de cada cliente; fuera de ese horario espera.</p>
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
  const { data } = useQuery({ queryKey: campaignKeys.recipients(c.id), queryFn: () => listRecipients(c.id), refetchInterval: c.status === "sending" || c.status === "scheduled" ? 15_000 : false });
  const cancelar = useMutation({ mutationFn: () => cancelCampaign(c.id), onSuccess: onChange });
  const s = c.audience.launch_summary;
  return (
    <div className="campaign-result">
      <div className="acta-title-row">
        <h2 className="acta-title">{c.name}</h2>
        <span className={`billing-chip ${ESTADO[c.status][1]}`}>{ESTADO[c.status][0]}</span>
      </div>
      <div className="campaign-preview"><small>Mensaje</small><p>{c.preview}</p></div>
      <dl className="acta-meta">
        <div><dt>Enviados</dt><dd>{c.stats.sent}</dd></div>
        <div><dt>En cola</dt><dd>{c.stats.pending}</dd></div>
        <div><dt>Fallidos</dt><dd>{c.stats.failed}</dd></div>
        <div><dt>No enviados</dt><dd>{c.stats.skipped}</dd></div>
        {s && <div><dt>Sin permiso (excluidos)</dt><dd>{s.without_consent + s.opted_out}</dd></div>}
      </dl>
      {(c.status === "scheduled" || c.status === "sending") && (
        <div className="acta-actions"><button type="button" className="acta-btn is-quiet" onClick={() => { if (window.confirm("¿Cancelar lo que falta por enviar?")) cancelar.mutate(); }}>Cancelar campaña</button></div>
      )}
      <div className="tablewrap"><table className="notices-table">
        <thead><tr><th>Cliente</th><th>Teléfono</th><th>Estado</th></tr></thead>
        <tbody>
          {(data ?? []).map((r) => (
            <tr key={r.id}>
              <td>{r.name}</td><td className="mono">{r.phone}</td>
              <td>{{ pending: "En cola", sent: "Enviado", failed: "Falló", skipped: "No enviado" }[r.status] ?? r.status}
                {r.status === "pending" && r.next_attempt_at && <small>sale {timeAgo(r.next_attempt_at).replace("hace ", "")}</small>}
                {r.last_error && <small className="notices-error">{r.last_error}</small>}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
    </div>
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
  const { data } = useQuery({ queryKey: campaignKeys.optOuts, queryFn: listOptOuts });
  const [tel, setTel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const agregar = useMutation({ mutationFn: () => addOptOut(tel, "Pidió no recibir más (registro manual)"),
    onSuccess: () => { setTel(""); setError(null); qc.invalidateQueries({ queryKey: campaignKeys.optOuts }); },
    onError: (e) => setError(apiErrorMessage(e)) });
  return (
    <article className="acta">
      <p className="acta-lead">Quien responde STOP sale de todas las campañas al instante. Si alguien lo pide por otro medio, regístralo aquí.</p>
      <form className="campaign-filters" onSubmit={(e) => { e.preventDefault(); agregar.mutate(); }}>
        <input aria-label="Teléfono" type="tel" placeholder="Teléfono" value={tel} onChange={(e) => setTel(e.target.value)} />
        <button type="submit" className="acta-btn is-line" disabled={tel.length < 7 || agregar.isPending}>Dar de baja</button>
      </form>
      {error && <p className="form-error" role="alert">{error}</p>}
      {(data ?? []).length === 0 ? <p className="acta-empty">Nadie se ha dado de baja.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Teléfono</th><th>Motivo</th><th>Cuándo</th></tr></thead>
          <tbody>{data!.map((o) => <tr key={o.phone}><td className="mono">{o.phone}</td><td>{o.reason}</td><td>{o.at ? timeAgo(o.at) : "—"}</td></tr>)}</tbody>
        </table></div>
      )}
    </article>
  );
}
