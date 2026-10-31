import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PaginatedTable, RowAction, RowActions } from "@/components/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { SearchPicker } from "@/components/SearchPicker";
import { confirmAction } from "@/components/ui/ConfirmDialog";
import { apiClient } from "@/lib/apiClient";
import { toast } from "@/lib/toast";
import { useClientPagination } from "@/lib/useClientPagination";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
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
  const [marcados, setMarcados] = useState<string[]>([]);
  const [reglas, setReglas] = useState(false);
  const [elegir, setElegir] = useState(false);
  const { data: estado } = useQuery({ queryKey: ["payments-status"], queryFn: getPaymentsStatus });
  const { data: conexiones } = useQuery({ queryKey: ["bank-connections"], queryFn: listConnections });
  const { data: conteo } = useQuery({ queryKey: ["bank-counts"], queryFn: getCounts });
  // Antes se pedía solo la primera página de 50: lo demás nunca se veía.
  const lista = usePaginatedQuery<BankTx>({ key: ["bank-tx"], path: "/bank-feeds/transactions", pageSize: 50,
    params: { status: tab, q: q || undefined, account_id: cuenta || undefined } });
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
  const filas = lista.items;
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
                onClick={() => { setTab(k); setMarcados([]); }}>
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
          <PaginatedTable list={lista} getRowKey={(t) => t.id} className="bank-table"
            emptyMessage={tab === "review" ? "Nada por revisar. Todo está al día." : "Sin movimientos."}
            rowClassName={(t) => (t.pending ? "is-pending" : undefined)}
            expandable={tab === "review" ? { render: (t) => <TxEditor t={t} onDone={refrescar} /> } : undefined}
            columns={[
              ...(tab === "review" ? [{ key: "elegir", header: "Elegir", render: (t: BankTx) => t.suggested_category && t.spent && !t.pending && (
                <input type="checkbox" checked={marcados.includes(t.id)} aria-label={`Seleccionar ${t.description}`}
                  onChange={(e) => setMarcados(e.target.checked ? [...marcados, t.id] : marcados.filter((x) => x !== t.id))} />
              ) }] : []),
              { key: "fecha", header: "Fecha", className: "bank-date", render: (t) => new Date(`${t.date}T12:00:00`).toLocaleDateString("es-US", { month: "short", day: "numeric" }) },
              { key: "descripcion", header: "Descripción", render: (t) => (
                <>
                  <strong>{t.merchant_name ?? t.description}</strong>{t.merchant_name && <small className="pay-muted">{t.description}</small>}
                  {t.pending && <small className="bank-pending">Pendiente en el banco</small>}
                </>
              ) },
              { key: "cuenta", header: "Cuenta", className: "pay-muted", render: (t) => (t.account ? `${t.account.name} ····${t.account.mask}` : "—") },
              { key: "gastado", header: "Gastado", className: "num", render: (t) => (t.spent ? usd(t.spent) : "") },
              { key: "recibido", header: "Recibido", className: "num is-in", render: (t) => (t.received ? usd(t.received) : "") },
              { key: "quedo", header: tab === "review" ? "Categoría o coincidencia" : "Quedó como", render: (t) => (tab === "review"
                ? (t.suggested_category ? <span className="bank-suggest">{t.suggested_by_rule ? "Regla: " : ""}{EXPENSE_CATEGORIES[t.suggested_category]}{t.project_title ? ` · ${t.project_title}` : ""}</span>
                  : <span className="pay-muted">Sin categoría</span>)
                : quedoComo(t)) },
              { key: "acciones", header: "", render: (t, fila) => (
                <RowActions>
                  {tab === "review"
                    ? <RowAction variant={fila.expanded ? "link" : "primary"} onClick={fila.toggle} disabled={t.pending}>
                        {fila.expanded ? "Cerrar" : t.spent ? "Agregar" : "Revisar"}</RowAction>
                    : <UndoTx t={t} onDone={refrescar} />}
                </RowActions>
              ) },
            ]} />
        </section>
      )}
    </div>
  );
}

/** Cómo quedó un movimiento ya revisado. */
function quedoComo(t: BankTx): string {
  return t.matched_type ? `Coincide con ${t.matched_type === "expense" ? "un gasto" : t.matched_type === "invoice_payment" ? "un pago de factura" : "un pago a proveedor"}`
    : t.category ? `${EXPENSE_CATEGORIES[t.category] ?? t.category}${t.project_title ? ` · ${t.project_title}` : ""}` : t.memo ?? "—";
}

/** «Deshacer» un movimiento ya revisado: vuelve a «Por revisar». */
function UndoTx({ t, onDone }: { t: BankTx; onDone: () => void }) {
  const deshacer = useMutation({ mutationFn: () => undoTx(t.id), onSuccess: onDone, onError: (e) => toast(apiError(e)) });
  return <RowAction disabled={deshacer.isPending} onClick={() => deshacer.mutate()}>Deshacer</RowAction>;
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
  const { data: reglas, isLoading: cargandoReglas } = useQuery({ queryKey: ["bank-rules"], queryFn: listRules });
  const listaReglas = useClientPagination(reglas, cargandoReglas);
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
      <PaginatedTable list={listaReglas} getRowKey={(r) => r.id} className="bank-table" emptyMessage="Sin reglas todavía."
        columns={[
          { key: "regla", header: "Regla", render: (r) => <strong>{r.name}</strong> },
          { key: "contiene", header: "Contiene", className: "pay-muted", render: (r) => `«${r.contains}»` },
          { key: "categoria", header: "Categoría", render: (r) => EXPENSE_CATEGORIES[r.category] ?? r.category },
          { key: "modo", header: "Modo", render: (r) => (r.auto_add ? "Agrega sola" : "Propone") },
          { key: "acciones", header: "", render: (r) => (
            <RowActions>
              <RowAction onClick={() => { setEditando(r.id); setForm({ ...r }); }}>Editar</RowAction>
              <RowAction variant="danger" onClick={async () => { await deleteRule(r.id); qc.invalidateQueries({ queryKey: ["bank-rules"] }); }}>Borrar</RowAction>
            </RowActions>
          ) },
        ]} />
    </section>
  );
}
