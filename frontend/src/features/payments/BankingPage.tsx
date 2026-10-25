import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/ui/PageHeader";
import { SearchPicker } from "@/components/SearchPicker";
import { confirmAction } from "@/components/ui/ConfirmDialog";
import { apiClient } from "@/lib/apiClient";
import { toast } from "@/lib/toast";
import {
  acceptTx, addTx, connectBank, deleteRule, disconnectBank, EXPENSE_CATEGORIES, excludeTx, getCandidates, getCounts,
  getLinkToken, getPaymentsStatus, listBankTx, listConnections, listRules, setAccountVisible, matchTx, saveRule, syncConnection, undoTx, usd,
  type BankRule, type BankTx,
} from "./api";
import "./payments.css";

type Obra = { id: string; title: string };
const TABS = [["review", "Por revisar"], ["categorized", "Categorizados"], ["excluded", "Excluidos"]] as const;

function apiError(e: unknown): string {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "No se pudo guardar.";
}
const buscarObras = (q: string) =>
  apiClient.get<Obra[]>("/projects", { params: { q: q || undefined, limit: 20 } }).then((r) => r.data);

/** Carga el script oficial de Plaid Link (la ventana segura donde la persona entra a su banco). */
function cargarPlaid(): Promise<{ create: (o: object) => { open: () => void } }> {
  const w = window as unknown as { Plaid?: { create: (o: object) => { open: () => void } } };
  if (w.Plaid) return Promise.resolve(w.Plaid);
  return new Promise((ok, mal) => {
    const s = document.createElement("script");
    s.src = "https://cdn.plaid.com/link/v2/stable/link-initialize.js";
    s.onload = () => (w.Plaid ? ok(w.Plaid) : mal(new Error("Plaid no cargó")));
    s.onerror = () => mal(new Error("Plaid no cargó"));
    document.head.appendChild(s);
  });
}

/**
 * Banca conectada, como «Banking» de QuickBooks: las cuentas y tarjetas de la
 * empresa arriba, y sus movimientos en «Por revisar», «Categorizados» y
 * «Excluidos». Cada compra se agrega como gasto de una obra, coincide con algo
 * ya registrado o se excluye; las reglas hacen solo lo que se repite.
 */
export function BankingPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("review");
  const [cuenta, setCuenta] = useState("");
  const [q, setQ] = useState("");
  const [abierto, setAbierto] = useState<string | null>(null);
  const [marcados, setMarcados] = useState<string[]>([]);
  const [reglas, setReglas] = useState(false);
  const [elegir, setElegir] = useState(false);
  const { data: estado } = useQuery({ queryKey: ["payments-status"], queryFn: getPaymentsStatus });
  const { data: conexiones } = useQuery({ queryKey: ["bank-connections"], queryFn: listConnections });
  const { data: conteo } = useQuery({ queryKey: ["bank-counts"], queryFn: getCounts });
  const { data: lista, isLoading } = useQuery({ queryKey: ["bank-tx", tab, cuenta, q],
    queryFn: () => listBankTx(tab, { q, account_id: cuenta }) });
  const refrescar = () => ["bank-tx", "bank-counts", "bank-connections"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));

  const conectar = useMutation({
    mutationFn: async () => {
      const [Plaid, token] = await Promise.all([cargarPlaid(), getLinkToken()]);
      await new Promise<void>((ok, mal) => {
        Plaid.create({
          token,
          onSuccess: async (public_token: string, meta: { institution?: { name?: string; institution_id?: string } }) => {
            try {
              await connectBank({ public_token, institution_name: meta.institution?.name ?? "Banco",
                institution_id: meta.institution?.institution_id });
              ok();
            } catch (e) { mal(e); }
          },
          onExit: () => ok(),
        }).open();
      });
    },
    onSuccess: () => { refrescar(); },
    onError: (e) => toast(apiError(e)),
  });
  const sincronizar = useMutation({
    mutationFn: (id: string) => syncConnection(id),
    onSuccess: (r) => { toast(`${r.added} movimientos nuevos`); refrescar(); },
    onError: (e) => toast(apiError(e)),
  });
  const aceptar = useMutation({
    mutationFn: () => acceptTx(marcados),
    onSuccess: (r) => { toast(`${r.accepted} agregados`); setMarcados([]); refrescar(); },
  });

  const cuentas = (conexiones ?? []).flatMap((c) => c.accounts.map((a) => ({ ...a, banco: c.institution_name, conexion: c })));
  const visibles = cuentas.filter((a) => a.active);
  const ocultas = cuentas.length - visibles.length;
  const filas = lista?.rows ?? [];
  const sugeridos = filas.filter((t) => t.suggested_category && !t.pending && t.spent);

  return (
    <div className="bank-page">
      <PageHeader eyebrow="Finanzas" title="Banca" description="Las compras de las tarjetas y los movimientos de las cuentas de la empresa llegan solos. Revísalos y cada uno queda en su obra."
        actions={<>
          <button type="button" className="acta-btn" onClick={() => setReglas((v) => !v)}>{reglas ? "Ver movimientos" : "Reglas"}</button>
          <button type="button" className="primary-button" disabled={!estado?.bank_feeds || conectar.isPending}
            onClick={() => conectar.mutate()}>{conectar.isPending ? "Conectando…" : "Conectar cuenta"}</button>
        </>} />

      {estado && !estado.bank_feeds && (
        <p className="pay-note">La banca conectada se activa cuando se configure la cuenta de Plaid de la empresa.</p>
      )}

      <div className="bank-accounts" role="list" aria-label="Cuentas conectadas">
        {visibles.map((a) => (
          <button key={a.id} type="button" role="listitem" className={`bank-account${cuenta === a.id ? " is-on" : ""}`}
            onClick={() => setCuenta(cuenta === a.id ? "" : a.id)}>
            <span className="bank-account-top">
              <span className="bank-chip">{a.type === "credit" ? "Tarjeta" : "Cuenta"}</span>
              <span className="pay-muted">{a.banco}</span>
            </span>
            <strong>{a.name} ····{a.mask}</strong>
            <span className="bank-balance">{usd(a.current_balance)}<small>{a.type === "credit" ? " saldo de la tarjeta" : " en el banco"}</small></span>
            <span className="pay-muted">
              {a.conexion.status === "needs_login" ? "Hay que volver a entrar al banco"
                : a.conexion.last_synced_at ? `Actualizada ${new Date(a.conexion.last_synced_at).toLocaleString("es-US", { dateStyle: "short", timeStyle: "short" })}` : "Sin sincronizar"}
            </span>
          </button>
        ))}
        {!cuentas.length && <p className="pay-muted">Todavía no hay cuentas conectadas.</p>}
      </div>
      {!!conexiones?.length && (
        <div className="bank-conn-actions">
          {conexiones.map((c) => (
            <span key={c.id}>
              <b>{c.institution_name}</b>
              <button type="button" className="link-button" onClick={() => sincronizar.mutate(c.id)}>Actualizar</button>
              <button type="button" className="link-button" aria-expanded={elegir} onClick={() => setElegir((v) => !v)}>
                Elegir cuentas{ocultas ? ` (${ocultas} ocultas)` : ""}</button>
              <button type="button" className="link-button" onClick={async () => {
                if (await confirmAction({ title: `Desconectar ${c.institution_name}`, danger: true, confirmLabel: "Desconectar",
                  message: "Dejan de llegar movimientos. Lo ya revisado se conserva." })) {
                  await disconnectBank(c.id); refrescar();
                }
              }}>Desconectar</button>
            </span>
          ))}
        </div>
      )}
      {elegir && (
        <fieldset className="bank-pick">
          <legend>Cuentas que se siguen</legend>
          <p className="pay-muted">De una cuenta oculta no llegan movimientos a revisar. Préstamos, hipoteca y ahorro para retiro llegan ocultos.</p>
          {cuentas.map((a) => (
            <label key={a.id}>
              <input type="checkbox" checked={a.active} onChange={async (e) => {
                try {
                  await setAccountVisible(a.id, e.target.checked);
                  if (!e.target.checked && cuenta === a.id) setCuenta("");
                  refrescar();
                } catch (err) { toast(apiError(err)); }
              }} />
              <span>{a.name} ····{a.mask}</span>
              <span className="pay-muted">{a.banco}</span>
            </label>
          ))}
        </fieldset>
      )}

      {reglas ? <RulesPanel /> : (
        <section className="bank-feed">
          <div className="bank-tabs" role="tablist">
            {TABS.map(([k, l]) => (
              <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "is-on" : ""}
                onClick={() => { setTab(k); setAbierto(null); setMarcados([]); }}>
                {l}{conteo?.[k] ? <span className={`bank-count${k === "review" ? "" : " is-quiet"}`}>{conteo[k]}</span> : null}
              </button>
            ))}
            <input className="bank-search" type="search" placeholder="Buscar por descripción o comercio" value={q}
              aria-label="Buscar movimientos" onChange={(e) => setQ(e.target.value)} />
          </div>
          {tab === "review" && sugeridos.length > 0 && (
            <div className="bank-batch">
              <label><input type="checkbox" checked={marcados.length === sugeridos.length && marcados.length > 0}
                onChange={(e) => setMarcados(e.target.checked ? sugeridos.map((t) => t.id) : [])} /> Seleccionar los propuestos por reglas ({sugeridos.length})</label>
              <button type="button" className="primary-button" disabled={!marcados.length || aceptar.isPending}
                onClick={() => aceptar.mutate()}>Aceptar {marcados.length || ""}</button>
            </div>
          )}
          <div className="table-wrap">
            <table className="bank-table">
              <thead><tr>
                {tab === "review" && <th aria-label="Seleccionar" />}
                <th>Fecha</th><th>Descripción</th><th>Cuenta</th><th className="num">Gastado</th><th className="num">Recibido</th>
                <th>{tab === "review" ? "Categoría o coincidencia" : "Quedó como"}</th><th>Acción</th>
              </tr></thead>
              <tbody>
                {isLoading && <tr><td colSpan={8}>Cargando…</td></tr>}
                {!isLoading && !filas.length && <tr><td colSpan={8} className="pay-muted">
                  {tab === "review" ? "Nada por revisar. Todo está al día." : "Sin movimientos."}</td></tr>}
                {filas.map((t) => (
                  <TxRow key={t.id} t={t} tab={tab} abierto={abierto === t.id} marcado={marcados.includes(t.id)}
                    onToggle={() => setAbierto(abierto === t.id ? null : t.id)}
                    onMark={(v) => setMarcados(v ? [...marcados, t.id] : marcados.filter((x) => x !== t.id))}
                    onDone={() => { setAbierto(null); refrescar(); }} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function TxRow({ t, tab, abierto, marcado, onToggle, onMark, onDone }: {
  t: BankTx; tab: string; abierto: boolean; marcado: boolean; onToggle: () => void; onMark: (v: boolean) => void; onDone: () => void;
}) {
  const quedo = t.matched_type ? `Coincide con ${t.matched_type === "expense" ? "un gasto" : t.matched_type === "invoice_payment" ? "un pago de factura" : "un pago a proveedor"}`
    : t.category ? `${EXPENSE_CATEGORIES[t.category] ?? t.category}${t.project_title ? ` · ${t.project_title}` : ""}` : t.memo ?? "—";
  const deshacer = useMutation({ mutationFn: () => undoTx(t.id), onSuccess: onDone, onError: (e) => toast(apiError(e)) });
  return (
    <>
      <tr className={`${abierto ? "is-open" : ""}${t.pending ? " is-pending" : ""}`}>
        {tab === "review" && <td>{t.suggested_category && t.spent && !t.pending &&
          <input type="checkbox" checked={marcado} aria-label={`Seleccionar ${t.description}`} onChange={(e) => onMark(e.target.checked)} />}</td>}
        <td className="bank-date">{new Date(`${t.date}T12:00:00`).toLocaleDateString("es-US", { month: "short", day: "numeric" })}</td>
        <td><strong>{t.merchant_name ?? t.description}</strong>{t.merchant_name && <small className="pay-muted">{t.description}</small>}
          {t.pending && <small className="bank-pending">Pendiente en el banco</small>}</td>
        <td className="pay-muted">{t.account ? `${t.account.name} ····${t.account.mask}` : "—"}</td>
        <td className="num">{t.spent ? usd(t.spent) : ""}</td>
        <td className="num is-in">{t.received ? usd(t.received) : ""}</td>
        <td>{tab === "review"
          ? (t.suggested_category ? <span className="bank-suggest">{t.suggested_by_rule ? "Regla: " : ""}{EXPENSE_CATEGORIES[t.suggested_category]}{t.project_title ? ` · ${t.project_title}` : ""}</span>
            : <span className="pay-muted">Sin categoría</span>)
          : quedo}</td>
        <td>{tab === "review"
          ? <button type="button" className={abierto ? "acta-btn" : "primary-button bank-action"} onClick={onToggle} disabled={t.pending}>
              {abierto ? "Cerrar" : t.spent ? "Agregar" : "Revisar"}</button>
          : <button type="button" className="link-button" onClick={() => deshacer.mutate()}>Deshacer</button>}</td>
      </tr>
      {abierto && <tr className="bank-editor-row"><td colSpan={8}><TxEditor t={t} onDone={onDone} /></td></tr>}
    </>
  );
}

function TxEditor({ t, onDone }: { t: BankTx; onDone: () => void }) {
  const [modo, setModo] = useState<"add" | "match">(t.spent ? "add" : "match");
  const [categoria, setCategoria] = useState(t.suggested_category ?? "small_materials");
  const [obra, setObra] = useState<Obra | null>(t.suggested_project_id ? { id: t.suggested_project_id, title: t.project_title ?? "Obra" } : null);
  const [memo, setMemo] = useState("");
  const [elegido, setElegido] = useState("");
  const { data: cands } = useQuery({ queryKey: ["bank-cands", t.id], queryFn: () => getCandidates(t.id) });
  const agregar = useMutation({ mutationFn: () => addTx(t.id, { category: categoria, project_id: obra?.id ?? null, memo: memo || null }),
    onSuccess: () => { toast("Agregado"); onDone(); }, onError: (e) => toast(apiError(e)) });
  const coincidir = useMutation({
    mutationFn: () => {
      const c = cands?.find((x) => x.id === elegido);
      if (!c) throw new Error("Elige con qué coincide.");
      return matchTx(t.id, c.type, c.id);
    },
    onSuccess: () => { toast("Coincidencia guardada"); onDone(); }, onError: (e) => toast(apiError(e)) });
  const excluir = useMutation({ mutationFn: () => excludeTx(t.id, memo || undefined),
    onSuccess: () => { toast("Excluido"); onDone(); }, onError: (e) => toast(apiError(e)) });

  return (
    <div className="bank-editor">
      <div className="bank-mode" role="radiogroup" aria-label="Qué hacer">
        {t.spent && <label><input type="radio" checked={modo === "add"} onChange={() => setModo("add")} /> Categorizar como gasto</label>}
        <label><input type="radio" checked={modo === "match"} onChange={() => setModo("match")} /> Buscar coincidencia
          {cands?.length ? <span className="bank-count">{cands.length}</span> : null}</label>
      </div>
      {modo === "add" ? (
        <div className="bank-form">
          <label>Categoría
            <select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              {Object.entries(EXPENSE_CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select></label>
          <label>Obra (opcional)
            <SearchPicker<Obra> label="Obra" value={obra} onChange={setObra} search={buscarObras} queryKey={["bank-obras"]}
              getKey={(o) => o.id} getLabel={(o) => o.title} pageSize={20} placeholder="Busca la obra" clearLabel="Quitar obra" /></label>
          <label>Nota<input value={memo} maxLength={500} onChange={(e) => setMemo(e.target.value)} placeholder="Para qué fue" /></label>
          <div className="bank-form-actions">
            <button type="button" className="link-button" onClick={() => excluir.mutate()}>Excluir</button>
            <button type="button" className="primary-button" disabled={agregar.isPending} onClick={() => agregar.mutate()}>Agregar</button>
          </div>
        </div>
      ) : (
        <div className="bank-form">
          {!cands?.length && <p className="pay-muted">No hay registros con el mismo monto en ±5 días.
            {t.received ? " Si es un depósito de Stripe o una transferencia, exclúyelo." : ""}</p>}
          {cands?.map((c) => (
            <label key={c.id} className="bank-cand">
              <input type="radio" name={`c-${t.id}`} checked={elegido === c.id} onChange={() => setElegido(c.id)} />
              <span>{c.label}</span><span className="pay-muted">{c.date}</span><b>{usd(c.amount)}</b>
              {c.has_receipt && <span className="bank-chip">Con recibo</span>}
            </label>
          ))}
          <div className="bank-form-actions">
            <button type="button" className="link-button" onClick={() => excluir.mutate()}>Excluir</button>
            <button type="button" className="primary-button" disabled={!elegido || coincidir.isPending} onClick={() => coincidir.mutate()}>Coincidir</button>
          </div>
        </div>
      )}
    </div>
  );
}

function RulesPanel() {
  const qc = useQueryClient();
  const { data: reglas } = useQuery({ queryKey: ["bank-rules"], queryFn: listRules });
  type Form = Partial<BankRule> & { name: string; contains: string; category: string; direction: BankRule["direction"]; auto_add: boolean };
  const vacia: Form = { name: "", contains: "", direction: "out", category: "small_materials", auto_add: false };
  const [form, setForm] = useState<Form>(vacia);
  const [editando, setEditando] = useState<string | undefined>();
  const guardar = useMutation({
    mutationFn: () => saveRule(form, editando),
    onSuccess: () => { toast("Regla guardada"); setForm(vacia); setEditando(undefined);
      ["bank-rules", "bank-tx"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); },
    onError: (e) => toast(apiError(e)),
  });
  return (
    <section className="bank-rules">
      <div className="panel">
        <h2>{editando ? "Editar regla" : "Nueva regla"}</h2>
        <p className="pay-muted">Si la descripción contiene el texto, se propone la categoría (y la obra). Con «Agregar sola», el gasto entra sin pasar por revisión.</p>
        <form className="bank-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
          <label>Nombre<input required value={form.name} maxLength={120} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Home Depot" /></label>
          <label>La descripción contiene<input required minLength={2} value={form.contains} maxLength={120}
            onChange={(e) => setForm({ ...form, contains: e.target.value })} placeholder="HOME DEPOT" /></label>
          <label>Movimientos
            <select value={form.direction} onChange={(e) => setForm({ ...form, direction: e.target.value as BankRule["direction"] })}>
              <option value="out">Gastos</option><option value="in">Depósitos</option><option value="any">Todos</option>
            </select></label>
          <label>Categoría
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {Object.entries(EXPENSE_CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select></label>
          <label className="bank-check"><input type="checkbox" checked={!!form.auto_add}
            onChange={(e) => setForm({ ...form, auto_add: e.target.checked })} /> Agregar sola</label>
          <div className="bank-form-actions">
            {editando && <button type="button" className="link-button" onClick={() => { setForm(vacia); setEditando(undefined); }}>Cancelar</button>}
            <button type="submit" className="primary-button" disabled={guardar.isPending}>Guardar regla</button>
          </div>
        </form>
      </div>
      <div className="table-wrap">
        <table className="bank-table">
          <thead><tr><th>Regla</th><th>Contiene</th><th>Categoría</th><th>Modo</th><th /></tr></thead>
          <tbody>
            {!(reglas ?? []).length && <tr><td colSpan={5} className="pay-muted">Sin reglas todavía.</td></tr>}
            {(reglas ?? []).map((r) => (
              <tr key={r.id}>
                <td><strong>{r.name}</strong></td><td className="pay-muted">«{r.contains}»</td>
                <td>{EXPENSE_CATEGORIES[r.category] ?? r.category}</td><td>{r.auto_add ? "Agrega sola" : "Propone"}</td>
                <td><button type="button" className="link-button" onClick={() => { setEditando(r.id); setForm({ ...r }); }}>Editar</button>{" "}
                  <button type="button" className="link-button" onClick={async () => {
                    await deleteRule(r.id); qc.invalidateQueries({ queryKey: ["bank-rules"] }); }}>Borrar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
