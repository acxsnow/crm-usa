import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "./programs.css";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { listUsers } from "@/features/users/api";
import { shortDay } from "@/features/billing/billingApi";
import type { Program } from "@/types/programs";
import {
  VERSION_STATUS,
  createProgram,
  createTerms,
  createVersion,
  createZone,
  installDefaults,
  listPrograms,
  listTerms,
  listVersions,
  listZones,
  programKeys,
  publishTerms,
  setZoneSalespeople,
  updateProgram,
  updateZone,
  useStates,
} from "./api";
import { FieldsCatalog } from "./FieldsCatalog";
import { CitySuggestions } from "@/components/CitySuggestions";

/**
 * Configuración de programas (módulo 1). Pestaña Programas: a la izquierda la
 * lista, a la derecha la hoja del elegido (identidad, versiones del
 * formulario, términos y zonas de venta). Pestaña Catálogo de campos: las
 * preguntas que los programas reutilizan.
 */
export function ProgramsPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "fields" ? "fields" : "programs";
  return (
    <div className="billing-page">
      <header className="billing-head">
        <h1>Configuración de programas</h1>
        <p>Qué pregunta cada programa, en qué orden, con qué términos y en qué zonas se vende.</p>
      </header>
      <nav className="billing-tabs" role="tablist" aria-label="Secciones">
        {[["programs", "Programas"], ["fields", "Catálogo de campos"]].map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k}
            className={`billing-tab${tab === k ? " is-active" : ""}`}
            onClick={() => setParams(k === "programs" ? {} : { tab: k })}>{l}</button>
        ))}
      </nav>
      {tab === "programs" ? <ProgramsTab /> : <FieldsCatalog />}
    </div>
  );
}

function ProgramsTab() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const puede = hasPermission("programs.manage");
  const { data: programas, isLoading } = useQuery({ queryKey: programKeys.list, queryFn: listPrograms });
  const [elegido, setElegido] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (!elegido && programas?.length) setElegido(programas[0].id); }, [programas, elegido]);
  const instalar = useMutation({
    mutationFn: installDefaults,
    onSuccess: () => qc.invalidateQueries({ queryKey: programKeys.list }),
    onError: (e) => setError(apiErrorMessage(e)),
  });

  if (isLoading) return <p className="acta-empty">Cargando…</p>;
  if (!programas?.length) {
    return (
      <section className="acta billing-list">
        <h2 className="acta-title">Todavía no hay programas</h2>
        <p className="acta-lead">Carga las plantillas del sistema: Eficiencia de Arizona y TECH Clean California con su
          formulario completo y el catálogo de campos. Después se ajustan desde aquí.</p>
        {error && <p className="form-error">{error}</p>}
        {puede && <button type="button" className="acta-btn is-primary" onClick={() => instalar.mutate()}
          disabled={instalar.isPending}>{instalar.isPending ? "Cargando…" : "Cargar plantillas del sistema"}</button>}
      </section>
    );
  }
  const actual = programas.find((p) => p.id === elegido);
  return (
    <div className="program-layout">
      <nav className="program-nav" aria-label="Programas">
        {programas.map((p) => (
          <button key={p.id} type="button" aria-current={p.id === elegido ? "true" : undefined}
            className={`program-nav-item${p.id === elegido ? " is-on" : ""}`} onClick={() => { setElegido(p.id); setNuevo(false); }}>
            <strong>{p.name}</strong>
            <span className={p.published_version ? undefined : "is-missing"}>
              {p.code} · {p.published_version ? `formulario v${p.published_version}` : "sin formulario publicado"}
            </span>
          </button>
        ))}
        {puede && !nuevo && <button type="button" className="acta-btn is-line" onClick={() => setNuevo(true)}>+ Nuevo programa</button>}
      </nav>
      {nuevo ? <NewProgram onDone={(id) => { setNuevo(false); setElegido(id); }} onCancel={() => setNuevo(false)} />
        : actual && <ProgramSheet key={actual.id} program={actual} />}
    </div>
  );
}

function NewProgram({ onDone, onCancel }: { onDone: (id: string) => void; onCancel: () => void }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const crear = useMutation({
    mutationFn: () => createProgram({ code, name }),
    onSuccess: async (p) => { await qc.invalidateQueries({ queryKey: programKeys.list }); onDone(p.id); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  return (
    <article className="acta program-sheet">
      <header className="acta-header"><h2 className="acta-title">Nuevo programa</h2></header>
      {error && <p className="form-error">{error}</p>}
      <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
        <div className="field"><label htmlFor="np-name">Nombre</label>
          <input id="np-name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="GoZero" autoFocus /></div>
        <div className="field"><label htmlFor="np-code">Código (no cambia después)</label>
          <input id="np-code" required value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="GOZERO" /></div>
        <div className="acta-actions">
          <button type="button" className="acta-btn is-quiet" onClick={onCancel}>Cancelar</button>
          <button type="submit" className="acta-btn is-primary" disabled={crear.isPending}>Crear programa</button>
        </div>
      </form>
    </article>
  );
}

function Section({ title, lead, action, children }: { title: string; lead: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="program-section">
      <div className="program-section-head"><div><h3>{title}</h3><p>{lead}</p></div>{action}</div>
      {children}
    </section>
  );
}

function ProgramSheet({ program }: { program: Program }) {
  const [error, setError] = useState<string | null>(null);
  return (
    <article className="acta program-sheet" aria-label={program.name}>
      <header className="acta-header">
        <div className="acta-title-row">
          <h2 className="acta-title">{program.name}</h2>
          <span className={`billing-chip ${program.active ? "is-paid" : "is-void"}`}>{program.active ? "Activo" : "Inactivo"}</span>
        </div>
        <dl className="acta-meta">
          <div><dt>Código</dt><dd className="acta-data">{program.code}</dd></div>
          <div><dt>Lo ve el cliente como</dt><dd>{program.customer_facing_name ?? program.name}</dd></div>
          <div><dt>Funder</dt><dd>{program.funder_name ?? "—"}</dd></div>
          <div><dt>Formulario vigente</dt><dd>{program.published_version ? `Versión ${program.published_version}` : "Ninguno publicado"}</dd></div>
        </dl>
      </header>
      {error && <p className="form-error" role="alert">{error}</p>}
      <Versions program={program} onError={setError} />
      <Terms program={program} onError={setError} />
      <Zones program={program} onError={setError} />
      <Identity program={program} onError={setError} />
    </article>
  );
}

type P = { program: Program; onError: (m: string | null) => void };

function Versions({ program, onError }: P) {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const { data } = useQuery({ queryKey: programKeys.part(program.id, "versions"), queryFn: () => listVersions(program.id) });
  const crear = useMutation({
    mutationFn: () => createVersion(program.id),
    onSuccess: () => { onError(null); return qc.invalidateQueries({ queryKey: programKeys.part(program.id, "versions") }); },
    onError: (e) => onError(apiErrorMessage(e)),
  });
  const versiones = [...(data ?? [])].reverse();
  const hayBorrador = versiones.some((v) => v.status === "draft");
  return (
    <Section title="Formulario del vendedor" lead="Cada versión publicada queda congelada: los expedientes guardan con cuál se llenaron. Para cambiar algo se crea una versión nueva que copia la vigente."
      action={hasPermission("workflows.manage") && !hayBorrador
        ? <button type="button" className="acta-btn is-line" onClick={() => crear.mutate()} disabled={crear.isPending}>+ Nueva versión</button> : undefined}>
      {versiones.length === 0 && <p className="acta-empty">Sin formulario todavía.</p>}
      <ul className="version-list">
        {versiones.map((v) => (
          <li key={v.id} className={`is-${v.status}`}>
            <Link to={`/programs/versions/${v.id}`}>
              <strong>Versión {v.version}</strong>
              <span className={`billing-chip ${v.status === "published" ? "is-paid" : v.status === "draft" ? "is-draft" : "is-void"}`}>{VERSION_STATUS[v.status]}</span>
              <span className="version-when">{v.published_at ? `publicada el ${shortDay(v.published_at)}` : `creada el ${shortDay(v.created_at)}`}</span>
              <span className="version-go">{v.status === "draft" ? "Editar ›" : "Ver ›"}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Terms({ program, onError }: P) {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const puede = hasPermission("programs.manage");
  const key = programKeys.part(program.id, "terms");
  const { data } = useQuery({ queryKey: key, queryFn: () => listTerms(program.id) });
  const [nuevo, setNuevo] = useState(false);
  const [form, setForm] = useState({ version: "", language: "es", title: "", body: "" });
  const [abierto, setAbierto] = useState<string | null>(null);
  const after = { onSuccess: () => { onError(null); setNuevo(false); return qc.invalidateQueries({ queryKey: key }); },
                  onError: (e: unknown) => onError(apiErrorMessage(e)) };
  const crear = useMutation({ mutationFn: () => createTerms(program.id, form), ...after });
  const publicar = useMutation({ mutationFn: (id: string) => publishTerms(id), ...after });
  return (
    <Section title="Autorización y términos" lead="El texto exacto que acepta el cliente, por versión e idioma. Publicado ya no se edita."
      action={puede && !nuevo ? <button type="button" className="acta-btn is-line" onClick={() => setNuevo(true)}>+ Nuevos términos</button> : undefined}>
      {(data ?? []).length === 0 && !nuevo && <p className="acta-empty">Sin términos cargados.</p>}
      <ul className="version-list">
        {(data ?? []).map((t) => (
          <li key={t.id}>
            <button type="button" className="version-row" onClick={() => setAbierto(abierto === t.id ? null : t.id)}>
              <strong>{t.version} · {t.language === "es" ? "Español" : "Inglés"}</strong>
              <span className={`billing-chip ${t.published_at ? "is-paid" : "is-draft"}`}>{t.published_at ? "Publicados" : "Borrador"}</span>
              <span className="version-when">{t.title}</span>
              <span className="version-go">{abierto === t.id ? "Cerrar" : "Leer"}</span>
            </button>
            {abierto === t.id && (
              <div className="terms-body">
                <p>{t.body}</p>
                {puede && !t.published_at && <button type="button" className="acta-btn is-primary" onClick={() => publicar.mutate(t.id)}>Publicar</button>}
              </div>
            )}
          </li>
        ))}
      </ul>
      {nuevo && (
        <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
          <div className="field"><label htmlFor="t-ver">Versión</label>
            <input id="t-ver" required value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} placeholder="2026.2" /></div>
          <div className="field"><label htmlFor="t-lang">Idioma</label>
            <select id="t-lang" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
              <option value="es">Español</option><option value="en">Inglés</option></select></div>
          <div className="field program-span"><label htmlFor="t-title">Título</label>
            <input id="t-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div className="field program-span"><label htmlFor="t-body">Texto completo</label>
            <textarea id="t-body" required value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} /></div>
          <div className="acta-actions">
            <button type="button" className="acta-btn is-quiet" onClick={() => setNuevo(false)}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={crear.isPending}>Guardar borrador</button>
          </div>
        </form>
      )}
    </Section>
  );
}

function Zones({ program, onError }: P) {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const puede = hasPermission("zones.manage");
  const key = programKeys.part(program.id, "zones");
  const { data } = useQuery({ queryKey: key, queryFn: () => listZones(program.id) });
  // Basta con ver la lista (`users.read`): asignar vendedores no es administrar usuarios.
  const { data: usuarios } = useQuery({ queryKey: ["users-all"], queryFn: listUsers,
                                        enabled: hasPermission("users.read") || hasPermission("users.manage") });
  const vendedores = (usuarios?.items ?? []).filter((u) => u.roles.includes("salesperson") && u.status === "active");
  const nombre = (id: string) => usuarios?.items.find((u) => u.id === id)?.full_name ?? "Vendedor";
  const [nueva, setNueva] = useState(false);
  const [form, setForm] = useState({ name: "", state: "AZ", city: "" });
  const estados = useStates();
  const [asignando, setAsignando] = useState<string | null>(null);
  const after = { onSuccess: () => { onError(null); return qc.invalidateQueries({ queryKey: key }); },
                  onError: (e: unknown) => onError(apiErrorMessage(e)) };
  const crear = useMutation({ mutationFn: () => createZone(program.id, form), ...after,
    onSuccess: () => { setNueva(false); setForm({ name: "", state: "AZ", city: "" }); onError(null); return qc.invalidateQueries({ queryKey: key }); } });
  const asignar = useMutation({ mutationFn: ({ id, ids }: { id: string; ids: string[] }) => setZoneSalespeople(id, ids), ...after });
  const alternar = useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => updateZone(id, { active }), ...after });

  return (
    <Section title="Zonas de venta" lead="Parques y comunidades donde se vende este programa, con sus vendedores. Cada vendedor ve en su inicio sus programas y zonas."
      action={puede && !nueva ? <button type="button" className="acta-btn is-line" onClick={() => setNueva(true)}>+ Agregar zona</button> : undefined}>
      {(data ?? []).length === 0 && !nueva && <p className="acta-empty">Sin zonas: ningún vendedor verá este programa en su inicio.</p>}
      <ul className="zone-list">
        {(data ?? []).map((z) => (
          <li key={z.id} className={z.active ? undefined : "is-off"}>
            <div className="zone-head">
              <div><strong>{z.name}</strong><span>{[z.city, z.state].filter(Boolean).join(", ") || "Sin ubicación"}</span></div>
              {puede && (
                <div className="acta-actions">
                  <button type="button" className="acta-btn is-quiet" onClick={() => setAsignando(asignando === z.id ? null : z.id)}>
                    {asignando === z.id ? "Listo" : "Vendedores"}
                  </button>
                  <button type="button" role="switch" aria-checked={z.active} aria-label={`${z.active ? "Desactivar" : "Activar"} ${z.name}`}
                    className={`req-switch${z.active ? " is-on" : ""}`} onClick={() => alternar.mutate({ id: z.id, active: !z.active })}><i /></button>
                </div>
              )}
            </div>
            <div className="zone-people">
              {z.salesperson_ids.length === 0 ? <span className="acta-empty">Sin vendedores</span>
                : z.salesperson_ids.map((id) => <span key={id} className="billing-file">{nombre(id)}</span>)}
            </div>
            {asignando === z.id && (
              <div className="zone-assign">
                {vendedores.length === 0 && <span className="acta-empty">No hay vendedores activos (o no tienes permiso para ver el equipo).</span>}
                {vendedores.map((u) => {
                  const on = z.salesperson_ids.includes(u.id);
                  return (
                    <label key={u.id} className={`form-choice${on ? " is-on" : ""}`}>
                      <input type="checkbox" checked={on} onChange={() => asignar.mutate({ id: z.id,
                        ids: on ? z.salesperson_ids.filter((x) => x !== u.id) : [...z.salesperson_ids, u.id] })} />
                      {u.full_name}
                    </label>
                  );
                })}
              </div>
            )}
          </li>
        ))}
      </ul>
      {nueva && (
        <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
          {/* Estado → ciudad → parque: las ciudades sugeridas dependen del estado. */}
          <div className="field"><label htmlFor="z-state">Estado</label>
            <select id="z-state" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} autoFocus>
              {estados.map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select></div>
          <div className="field"><label htmlFor="z-city">Ciudad</label>
            <input id="z-city" list="z-city-options" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} placeholder="Phoenix" />
            <CitySuggestions id="z-city-options" state={form.state} value={form.city} /></div>
          <div className="field"><label htmlFor="z-name">Parque o comunidad</label>
            <input id="z-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Sunrise Mobile Park" /></div>
          <div className="acta-actions">
            <button type="button" className="acta-btn is-quiet" onClick={() => setNueva(false)}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={crear.isPending}>Guardar zona</button>
          </div>
        </form>
      )}
    </Section>
  );
}

function Identity({ program, onError }: P) {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const [editando, setEditando] = useState(false);
  const [form, setForm] = useState<Partial<Program>>(program);
  useEffect(() => setForm(program), [program]);
  const guardar = useMutation({
    mutationFn: () => updateProgram(program.id, {
      name: form.name, active: form.active, customer_facing_name: form.customer_facing_name,
      funder_name: form.funder_name, invoice_entity: form.invoice_entity, logo_url: form.logo_url,
      authorization_text: form.authorization_text, description: form.description,
    }),
    onSuccess: () => { onError(null); setEditando(false); return qc.invalidateQueries({ queryKey: programKeys.list }); },
    onError: (e) => onError(apiErrorMessage(e)),
  });
  const campo = (k: keyof Program, label: string) => (
    <div className="field"><label htmlFor={`pi-${k}`}>{label}</label>
      <input id={`pi-${k}`} value={(form[k] as string | null) ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>
  );
  return (
    <Section title="Identidad frente al cliente" lead="Quién aparece ante el cliente y en la factura. La organización que opera, el funder y quien factura pueden ser distintos."
      action={hasPermission("programs.manage") && !editando ? <button type="button" className="acta-btn is-line" onClick={() => setEditando(true)}>Editar</button> : undefined}>
      {!editando ? (
        <dl className="profile-view">
          <div><dt>Nombre que ve el cliente</dt><dd>{program.customer_facing_name ?? program.name}</dd></div>
          <div><dt>Funder</dt><dd>{program.funder_name ?? "—"}</dd></div>
          <div><dt>Factura</dt><dd>{program.invoice_entity ?? "—"}</dd></div>
          <div><dt>Estado</dt><dd>{program.active ? "Activo" : "Inactivo: no aparece a los vendedores"}</dd></div>
          <div className="program-span"><dt>Texto de autorización</dt><dd className="profile-legal">{program.authorization_text ?? "Sin texto."}</dd></div>
        </dl>
      ) : (
        <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
          {campo("name", "Nombre interno")}
          {campo("customer_facing_name", "Nombre que ve el cliente")}
          {campo("funder_name", "Funder")}
          {campo("invoice_entity", "Entidad que factura")}
          {campo("logo_url", "Logo (URL)")}
          <label className="billing-check"><input type="checkbox" checked={Boolean(form.active)}
            onChange={(e) => setForm({ ...form, active: e.target.checked })} /> Activo</label>
          <div className="field program-span"><label htmlFor="pi-auth">Texto de autorización</label>
            <textarea id="pi-auth" value={form.authorization_text ?? ""} onChange={(e) => setForm({ ...form, authorization_text: e.target.value })} /></div>
          <div className="acta-actions program-span">
            <button type="button" className="acta-btn is-quiet" onClick={() => { setForm(program); setEditando(false); }}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>Guardar</button>
          </div>
        </form>
      )}
    </Section>
  );
}
