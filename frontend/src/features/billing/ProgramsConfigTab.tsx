import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import type { ProgramProfile, ProgramRate, ProgramRequirement } from "@/types/billing";
import {
  addJurisdiction,
  addRate,
  addRequirement,
  billingKeys,
  closeRate,
  deleteJurisdiction,
  getAutoRules,
  getProfile,
  listBillingPrograms,
  listJurisdictions,
  listRates,
  listRequirements,
  money,
  shortDay,
  updateProfile,
  updateRequirement,
} from "./billingApi";

const hoyISO = () => new Date().toISOString().slice(0, 10);
const vigente = (r: { valid_from: string; valid_to: string | null }, d = hoyISO()) =>
  r.valid_from <= d && (!r.valid_to || r.valid_to >= d);

/**
 * Configuración de cobro por programa (spec D6.2). A la izquierda los
 * programas; a la derecha la hoja del elegido: lo que decide cada cobro hoy
 * arriba, y debajo tarifas, zonas, checklist y datos de la factura. Cambiar
 * exige `billing.configure`; los demás la ven en solo lectura.
 */
export function ProgramsConfigTab() {
  const { data: programas } = useQuery({ queryKey: billingKeys.programs, queryFn: listBillingPrograms });
  const [elegido, setElegido] = useState<string>("");
  useEffect(() => { if (!elegido && programas?.length) setElegido(programas[0].id); }, [programas, elegido]);
  const { hasPermission } = useAuth();
  const editable = hasPermission("billing.configure");

  if (programas && programas.length === 0) {
    return (
      <section className="acta billing-list">
        <p className="acta-empty">No hay programas creados. El catálogo de programas llega con el módulo 1 (Cadena A).</p>
      </section>
    );
  }
  const actual = (programas ?? []).find((p) => p.id === elegido);
  return (
    <div className="program-layout">
      <nav className="program-nav" aria-label="Programas">
        {(programas ?? []).map((p) => (
          <ProgramNavItem key={p.id} id={p.id} name={p.name} active={p.id === elegido} onSelect={() => setElegido(p.id)} />
        ))}
      </nav>
      {actual && <ProgramSheet key={actual.id} programId={actual.id} name={actual.name} editable={editable} />}
    </div>
  );
}

function ProgramNavItem({ id, name, active, onSelect }: { id: string; name: string; active: boolean; onSelect: () => void }) {
  const { data: rates } = useQuery({ queryKey: billingKeys.program(id, "rates"), queryFn: () => listRates(id) });
  const tarifa = (rates ?? []).find((r) => vigente(r));
  return (
    <button type="button" aria-current={active ? "true" : undefined} className={`program-nav-item${active ? " is-on" : ""}`} onClick={onSelect}>
      <strong>{name}</strong>
      <span className={tarifa ? "money" : "is-missing"}>{tarifa ? money(tarifa.amount) : "Sin tarifa vigente"}</span>
    </button>
  );
}

type Props = { programId: string; editable: boolean; onError: (m: string | null) => void };

/** Manejo común de las mutaciones: limpiar o mostrar el error y refrescar esa parte. */
function useAct(programId: string, part: string, onError: Props["onError"]) {
  const qc = useQueryClient();
  return (after?: () => void) => ({
    onSuccess: () => { onError(null); after?.(); return qc.invalidateQueries({ queryKey: billingKeys.program(programId, part) }); },
    onError: (e: unknown) => onError(apiErrorMessage(e)),
  });
}

function ProgramSheet({ programId, name, editable }: { programId: string; name: string; editable: boolean }) {
  const [error, setError] = useState<string | null>(null);
  const common = { programId, editable, onError: setError };
  const { data: rates } = useQuery({ queryKey: billingKeys.program(programId, "rates"), queryFn: () => listRates(programId) });
  const { data: zonas } = useQuery({ queryKey: billingKeys.program(programId, "jurisdictions"), queryFn: () => listJurisdictions(programId) });
  const { data: reqs } = useQuery({ queryKey: billingKeys.program(programId, "requirements"), queryFn: () => listRequirements(programId) });
  const { data: perfil } = useQuery({ queryKey: billingKeys.program(programId, "profile"), queryFn: () => getProfile(programId) });
  const tarifa = (rates ?? []).find((r) => vigente(r));
  const zonasHoy = (zonas ?? []).filter((z) => vigente(z));
  return (
    <article className="acta program-sheet" aria-label={`Configuración de ${name}`}>
      <header className="acta-header">
        <div className="acta-title-row">
          <h2 className="acta-title">{name}</h2>
          <span className="acta-amount money">{tarifa ? money(tarifa.amount) : "Sin tarifa"}</span>
        </div>
        <dl className="acta-meta">
          <div><dt>Tarifa vigente</dt><dd>{tarifa ? `hasta ${tarifa.valid_to ? shortDay(tarifa.valid_to) : "nuevo aviso"}` : "Cárgala para poder cobrar"}</dd></div>
          <div><dt>Aplica en</dt><dd>{zonasHoy.length ? zonasHoy.map((z) => z.label).join(", ") : "Ninguna zona vigente"}</dd></div>
          <div><dt>Para radicar pide</dt><dd>{(reqs ?? []).filter((r) => r.active).length} requisitos</dd></div>
          <div><dt>Suele pagar en</dt><dd>{perfil ? `${perfil.expected_payment_days} días` : "—"}</dd></div>
        </dl>
      </header>
      {error && <p className="form-error" role="alert">{error}</p>}
      <Rates {...common} rates={rates ?? []} />
      <Zones {...common} />
      <Requirements {...common} reqs={reqs ?? []} />
      <Profile {...common} perfil={perfil} />
    </article>
  );
}

function Section({ title, lead, action, children }: { title: string; lead: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="program-section">
      <div className="program-section-head">
        <div><h3>{title}</h3><p>{lead}</p></div>
        {action}
      </div>
      {children}
    </section>
  );
}

// --- Tarifas -----------------------------------------------------------------

function Rates({ programId, editable, onError, rates }: Props & { rates: ProgramRate[] }) {
  const act = useAct(programId, "rates", onError);
  const [nueva, setNueva] = useState(false);
  const [monto, setMonto] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [cerrando, setCerrando] = useState<string | null>(null);
  const [cierre, setCierre] = useState("");
  const agregar = useMutation({
    mutationFn: () => addRate(programId, { amount: Number(monto), valid_from: desde, valid_to: hasta || undefined }),
    ...act(() => { setMonto(""); setDesde(""); setHasta(""); setNueva(false); }),
  });
  const cerrar = useMutation({ mutationFn: () => closeRate(cerrando!, cierre), ...act(() => { setCerrando(null); setCierre(""); }) });
  const hoy = hoyISO();
  const orden = [...rates].sort((a, b) => b.valid_from.localeCompare(a.valid_from));

  return (
    <Section title="Tarifa por instalación" lead="Vale la que estaba vigente el día de la instalación, aunque se cobre después."
      action={editable && !nueva ? <button type="button" className="acta-btn is-line" onClick={() => setNueva(true)}>+ Nueva tarifa</button> : undefined}>
      {orden.length === 0 && !nueva && <p className="acta-empty">Sin tarifas: no se puede crear ningún cobro de este programa.</p>}
      <div className="rate-cards">
        {orden.map((r) => {
          const estado = vigente(r, hoy) ? "is-current" : r.valid_from > hoy ? "is-future" : "is-past";
          return (
            <div key={r.id} className={`rate-card ${estado}`}>
              <span className="rate-year">{r.valid_from.slice(0, 4)}</span>
              <strong className="money">{money(r.amount)}</strong>
              <span className="rate-period">{shortDay(r.valid_from)} – {r.valid_to ? shortDay(r.valid_to) : "sin fin"}</span>
              <span className="rate-tag">{estado === "is-current" ? "Vigente" : estado === "is-future" ? "Próxima" : "Anterior"}</span>
              {editable && !r.valid_to && cerrando !== r.id && (
                <button type="button" className="rate-close" onClick={() => setCerrando(r.id)}>Cerrar vigencia</button>
              )}
              {cerrando === r.id && (
                <form className="rate-close-form" onSubmit={(e) => { e.preventDefault(); cerrar.mutate(); }}>
                  <input type="date" aria-label="Último día de esta tarifa" required value={cierre} onChange={(e) => setCierre(e.target.value)} />
                  <div className="acta-actions">
                    <button type="submit" className="acta-btn is-primary">Cerrar</button>
                    <button type="button" className="acta-btn is-quiet" onClick={() => setCerrando(null)}>Cancelar</button>
                  </div>
                </form>
              )}
            </div>
          );
        })}
      </div>
      {nueva && (
        <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); agregar.mutate(); }}>
          <div className="field"><label htmlFor="t-monto">Monto por instalación (USD)</label>
            <input id="t-monto" type="number" step="0.01" min="0.01" required value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="4000" autoFocus /></div>
          <div className="field"><label htmlFor="t-desde">Desde</label>
            <input id="t-desde" type="date" required value={desde} onChange={(e) => setDesde(e.target.value)} /></div>
          <div className="field"><label htmlFor="t-hasta">Hasta (si ya se sabe)</label>
            <input id="t-hasta" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></div>
          <div className="acta-actions">
            <button type="button" className="acta-btn is-quiet" onClick={() => setNueva(false)}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={agregar.isPending}>Guardar tarifa</button>
          </div>
        </form>
      )}
    </Section>
  );
}

// --- Zonas -------------------------------------------------------------------

function Zones({ programId, editable, onError }: Props) {
  const { data } = useQuery({ queryKey: billingKeys.program(programId, "jurisdictions"), queryFn: () => listJurisdictions(programId) });
  const act = useAct(programId, "jurisdictions", onError);
  const [nueva, setNueva] = useState(false);
  const [tipo, setTipo] = useState("city");
  const [valor, setValor] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const agregar = useMutation({
    mutationFn: () => addJurisdiction(programId, { kind: tipo, value: valor, valid_from: desde, valid_to: hasta || undefined }),
    ...act(() => { setValor(""); setNueva(false); }),
  });
  const quitar = useMutation({ mutationFn: (id: string) => deleteJurisdiction(id), ...act() });
  const hoy = hoyISO();

  return (
    <Section title="Dónde aplica" lead="Por ciudad o código postal. La zona cambia cada año, así que cada una tiene vigencia."
      action={editable && !nueva ? <button type="button" className="acta-btn is-line" onClick={() => setNueva(true)}>+ Agregar zona</button> : undefined}>
      {(data ?? []).length === 0 && !nueva && <p className="acta-empty">Sin zonas: ninguna dirección aparecerá como elegible.</p>}
      <ul className="zone-chips">
        {(data ?? []).map((z) => (
          <li key={z.id} className={vigente(z, hoy) ? "is-current" : "is-past"}>
            <strong>{z.label}</strong>
            <span>{z.kind === "city" ? "Ciudad" : "Código postal"} · {shortDay(z.valid_from)} – {z.valid_to ? shortDay(z.valid_to) : "sin fin"}</span>
            {editable && (
              <button type="button" aria-label={`Quitar ${z.label}`} onClick={() => quitar.mutate(z.id)}>×</button>
            )}
          </li>
        ))}
      </ul>
      {nueva && (
        <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); agregar.mutate(); }}>
          <div className="field"><label htmlFor="j-tipo">Por</label>
            <select id="j-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="city">Ciudad</option><option value="zip">Código postal</option>
            </select></div>
          <div className="field"><label htmlFor="j-valor">{tipo === "city" ? "Ciudad" : "Código postal"}</label>
            <input id="j-valor" required value={valor} onChange={(e) => setValor(e.target.value)} autoFocus
              placeholder={tipo === "city" ? "San Fernando" : "91340"} /></div>
          <div className="field"><label htmlFor="j-desde">Desde</label>
            <input id="j-desde" type="date" required value={desde} onChange={(e) => setDesde(e.target.value)} /></div>
          <div className="field"><label htmlFor="j-hasta">Hasta (si ya se sabe)</label>
            <input id="j-hasta" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></div>
          <div className="acta-actions">
            <button type="button" className="acta-btn is-quiet" onClick={() => setNueva(false)}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={agregar.isPending}>Guardar zona</button>
          </div>
        </form>
      )}
    </Section>
  );
}

// --- Checklist ------------------------------------------------------------------

function Requirements({ programId, editable, onError, reqs }: Props & { reqs: ProgramRequirement[] }) {
  const { data: reglas } = useQuery({ queryKey: ["billing-auto-rules"], queryFn: getAutoRules, staleTime: Infinity });
  const act = useAct(programId, "requirements", onError);
  const [nuevo, setNuevo] = useState(false);
  const [texto, setTexto] = useState("");
  const [regla, setRegla] = useState("");
  const alternar = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => updateRequirement(id, { active }), ...act(),
  });
  const agregar = useMutation({
    mutationFn: () => addRequirement(programId, regla ? { auto_code: regla } : { label: texto }),
    ...act(() => { setTexto(""); setRegla(""); setNuevo(false); }),
  });
  const usadas = new Set(reqs.map((r) => r.code));
  const grupo = (kind: "manual" | "auto", titulo: string) => {
    const lista = reqs.filter((r) => r.kind === kind);
    if (!lista.length) return null;
    return (
      <div className="req-group">
        <h4>{titulo}</h4>
        <ul>
          {lista.map((r) => (
            <li key={r.id} className={r.active ? undefined : "is-off"}>
              <span>{r.label}</span>
              <button type="button" role="switch" aria-checked={r.active} disabled={!editable}
                aria-label={`${r.active ? "Desactivar" : "Activar"} ${r.label}`}
                className={`req-switch${r.active ? " is-on" : ""}`} onClick={() => alternar.mutate({ id: r.id, active: !r.active })}>
                <i />
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <Section title="Checklist para radicar" lead="Sin todo lo activo no se radica. Apaga lo que este programa no pide (TECH sin inspección, por ejemplo)."
      action={editable && !nuevo ? <button type="button" className="acta-btn is-line" onClick={() => setNuevo(true)}>+ Agregar requisito</button> : undefined}>
      <div className="req-groups">
        {grupo("manual", "Los confirma una persona en cada cobro")}
        {grupo("auto", "Los comprueba el sistema")}
      </div>
      {nuevo && (
        <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); agregar.mutate(); }}>
          <div className="field"><label htmlFor="r-regla">Tipo</label>
            <select id="r-regla" value={regla} onChange={(e) => setRegla(e.target.value)}>
              <option value="">Lo confirma una persona</option>
              {Object.entries(reglas ?? {}).filter(([k]) => !usadas.has(k)).map(([k, v]) => <option key={k} value={k}>Sistema: {v}</option>)}
            </select></div>
          {!regla && (
            <div className="field program-span"><label htmlFor="r-nuevo">Qué hay que confirmar</label>
              <input id="r-nuevo" required value={texto} onChange={(e) => setTexto(e.target.value)} autoFocus
                placeholder="Formulario de reducción de carbono" /></div>
          )}
          <div className="acta-actions">
            <button type="button" className="acta-btn is-quiet" onClick={() => setNuevo(false)}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={agregar.isPending}>Agregar</button>
          </div>
        </form>
      )}
    </Section>
  );
}

// --- Datos de la factura -----------------------------------------------------------

function Profile({ programId, editable, onError, perfil }: Props & { perfil: ProgramProfile | undefined }) {
  const act = useAct(programId, "profile", onError);
  const [editando, setEditando] = useState(false);
  const [form, setForm] = useState<Partial<ProgramProfile>>({});
  useEffect(() => { if (perfil) setForm(perfil); }, [perfil]);
  const guardar = useMutation({
    mutationFn: () => updateProfile(programId, {
      issuer_name: form.issuer_name, issuer_address: form.issuer_address, issuer_phone: form.issuer_phone,
      issuer_email: form.issuer_email, legal_text: form.legal_text, expected_payment_days: Number(form.expected_payment_days),
    }),
    ...act(() => setEditando(false)),
  });
  const campo = (k: keyof ProgramProfile, label: string, placeholder = "") => (
    <div className="field"><label htmlFor={`pf-${k}`}>{label}</label>
      <input id={`pf-${k}`} value={(form[k] as string | number | null) ?? ""} placeholder={placeholder}
        onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>
  );

  return (
    <Section title="Datos de la factura" lead="Quién factura a este programa y el texto legal que va al pie del PDF."
      action={editable && !editando ? <button type="button" className="acta-btn is-line" onClick={() => setEditando(true)}>Editar</button> : undefined}>
      {!editando ? (
        <dl className="profile-view">
          <div><dt>Factura</dt><dd>{perfil?.issuer_name ?? "La organización"}</dd></div>
          <div><dt>Dirección</dt><dd>{perfil?.issuer_address ?? "—"}</dd></div>
          <div><dt>Contacto</dt><dd>{[perfil?.issuer_phone, perfil?.issuer_email].filter(Boolean).join(" · ") || "—"}</dd></div>
          <div><dt>Alerta de pago</dt><dd>a los {perfil?.expected_payment_days ?? 45} días de radicado</dd></div>
          <div className="program-span"><dt>Texto legal</dt><dd className="profile-legal">{perfil?.legal_text || "Sin texto legal."}</dd></div>
        </dl>
      ) : (
        <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
          {campo("issuer_name", "Entidad que factura", "Delta HVAC Service Inc.")}
          {campo("issuer_address", "Dirección")}
          {campo("issuer_phone", "Teléfono")}
          {campo("issuer_email", "Correo")}
          <div className="field"><label htmlFor="pf-dias">Alerta de pago (días)</label>
            <input id="pf-dias" type="number" min={1} max={365} value={form.expected_payment_days ?? 45}
              onChange={(e) => setForm({ ...form, expected_payment_days: Number(e.target.value) })} /></div>
          <div className="field program-span"><label htmlFor="pf-legal">Texto legal (en inglés, va en el PDF)</label>
            <textarea id="pf-legal" value={form.legal_text ?? ""} onChange={(e) => setForm({ ...form, legal_text: e.target.value })} /></div>
          <div className="acta-actions program-span">
            <button type="button" className="acta-btn is-quiet" onClick={() => { setForm(perfil ?? {}); setEditando(false); }}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>Guardar</button>
          </div>
        </form>
      )}
    </Section>
  );
}
