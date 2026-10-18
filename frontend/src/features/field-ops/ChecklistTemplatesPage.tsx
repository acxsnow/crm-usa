import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "./checklists.css";
import { listPrograms, programKeys } from "@/features/programs/api";
import type { ChecklistTemplate, ChecklistTemplateItem } from "@/types/fieldOps";
import {
  createChecklistTemplate,
  deleteChecklistTemplate,
  listChecklistTemplates,
  seedDefaultChecklistTemplate,
  updateChecklistTemplate,
} from "./api";
import { apiErrorMessage, useFieldCatalogs } from "./module5Api";

type Item = Omit<ChecklistTemplateItem, "id">;
const DEFAULT = "__default__";
const KEY = ["checklist-templates"] as const;

/**
 * Checklists de instalación por programa (pendiente del módulo 5). Cada
 * programa puede tener su plantilla; el que no la tiene usa la de la
 * organización. Editar una plantilla no cambia las instalaciones que ya la
 * usaron: al aplicarse, sus ítems se copian al proyecto.
 */
export function ChecklistTemplatesPage() {
  const { data: plantillas, isLoading } = useQuery({ queryKey: KEY, queryFn: listChecklistTemplates });
  const { data: programas } = useQuery({ queryKey: programKeys.list, queryFn: listPrograms });
  const [sel, setSel] = useState<string>(DEFAULT);

  const porPrograma = (pid: string | null) => (plantillas ?? []).find((t) => (t.program_id ?? null) === pid);
  const defecto = porPrograma(null);
  const activos = (programas ?? []).filter((p) => p.active);

  return (
    <div className="billing-page checklists-page">
      <header className="billing-head">
        <div>
          <h1>Checklists de instalación</h1>
          <p>Lo que el técnico debe completar al instalar. Cada programa puede tener el suyo; si no, usa el de la organización.</p>
        </div>
      </header>
      {isLoading ? <p className="acta-empty">Cargando…</p> : (
        <div className="checklists-grid">
          <nav className="acta checklists-list" aria-label="Plantillas">
            <button type="button" className={sel === DEFAULT ? "is-on" : ""} onClick={() => setSel(DEFAULT)}>
              <strong>Por defecto de la organización</strong>
              <small>{defecto ? `${defecto.items.length} ítems` : "Sin crear"}</small>
            </button>
            <h2 className="acta-section-title">Programas</h2>
            {activos.length === 0 && <p className="acta-empty">No hay programas activos.</p>}
            {activos.map((p) => {
              const t = porPrograma(p.id);
              return (
                <button key={p.id} type="button" className={sel === p.id ? "is-on" : ""} onClick={() => setSel(p.id)}>
                  <strong>{p.name}</strong>
                  <small>{t ? `${t.items.length} ítems` : "Usa la por defecto"}</small>
                </button>
              );
            })}
          </nav>
          <Editor key={sel} programId={sel === DEFAULT ? null : sel}
            programName={sel === DEFAULT ? null : activos.find((p) => p.id === sel)?.name ?? null}
            template={sel === DEFAULT ? defecto : porPrograma(sel)} fallback={defecto} />
        </div>
      )}
    </div>
  );
}

function sinId(items: ChecklistTemplateItem[]): Item[] {
  return items.map(({ id: _id, ...resto }) => resto);
}

const vacio = (n: number): Item => ({ label: "", sort_order: n, is_required: true, requires_evidence: false, section: null,
  evidence_category: null, condition_code: null, allows_not_applicable: false });

function Editor({ programId, programName, template, fallback }: {
  programId: string | null; programName: string | null; template?: ChecklistTemplate; fallback?: ChecklistTemplate;
}) {
  const qc = useQueryClient();
  const { data: cat } = useFieldCatalogs();
  const [nombre, setNombre] = useState(template?.name ?? (programName ? `Instalación ${programName}` : "Checklist de instalación"));
  const [items, setItems] = useState<Item[]>(template ? sinId(template.items) : []);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [editando, setEditando] = useState(!!template);
  useEffect(() => { setAviso(null); }, [items, nombre]);

  const listo = () => qc.invalidateQueries({ queryKey: KEY });
  const guardar = useMutation({
    mutationFn: () => {
      const body = { name: nombre.trim(), program_id: programId,
        items: items.filter((i) => i.label.trim()).map((i, n) => ({ ...i, label: i.label.trim(), sort_order: n + 1 })) };
      return template ? updateChecklistTemplate(template.id, body) : createChecklistTemplate(body);
    },
    onSuccess: async () => { setError(null); await listo(); },
    onError: (e) => setError(apiErrorMessage(e)),
    meta: { successMessage: "Guardado. Se aplica a las próximas instalaciones." },
  });
  const borrar = useMutation({
    mutationFn: () => deleteChecklistTemplate(template!.id),
    onSuccess: listo, onError: (e) => setError(apiErrorMessage(e)),
  });
  const sembrar = useMutation({ mutationFn: seedDefaultChecklistTemplate, onSuccess: listo, onError: (e) => setError(apiErrorMessage(e)) });

  const cambiar = (n: number, cambio: Partial<Item>) => setItems((xs) => xs.map((x, i) => (i === n ? { ...x, ...cambio } : x)));
  const mover = (n: number, d: -1 | 1) => setItems((xs) => {
    const m = n + d;
    if (m < 0 || m >= xs.length) return xs;
    const c = [...xs];
    [c[n], c[m]] = [c[m], c[n]];
    return c;
  });

  if (!template && !editando) {
    return (
      <article className="acta checklists-editor">
        <h2>{programName ?? "Por defecto de la organización"}</h2>
        {programId ? (
          <>
            <p className="acta-lead">Este programa usa el checklist por defecto{fallback ? ` (${fallback.items.length} ítems)` : ""}.
              Crea uno propio si sus instalaciones piden algo distinto.</p>
            <div className="acta-actions">
              {fallback && <button type="button" className="acta-btn is-primary" onClick={() => { setItems(sinId(fallback.items)); setEditando(true); }}>
                Partir del por defecto</button>}
              <button type="button" className="acta-btn is-line" onClick={() => { setItems([vacio(1)]); setEditando(true); }}>Empezar vacío</button>
            </div>
          </>
        ) : (
          <>
            <p className="acta-lead">La organización todavía no tiene checklist por defecto.</p>
            <div className="acta-actions">
              <button type="button" className="acta-btn is-primary" disabled={sembrar.isPending} onClick={() => sembrar.mutate()}>
                Cargar el estándar de HVAC</button>
              <button type="button" className="acta-btn is-line" onClick={() => { setItems([vacio(1)]); setEditando(true); }}>Empezar vacío</button>
            </div>
          </>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
      </article>
    );
  }

  return (
    <article className="acta checklists-editor">
      <form onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
        <div className="checklists-head">
          <div className="form-field">
            <label className="form-label" htmlFor="ck-name">Nombre</label>
            <input id="ck-name" value={nombre} onChange={(e) => setNombre(e.target.value)} required maxLength={255} />
          </div>
          <span className="billing-chip is-submitted">{programName ?? "Por defecto"}</span>
        </div>

        <ol className="checklists-items">
          {items.map((it, n) => (
            <li key={n} className="checklists-item">
              <div className="checklists-order">
                <span>{n + 1}</span>
                <button type="button" aria-label="Subir" disabled={n === 0} onClick={() => mover(n, -1)}>↑</button>
                <button type="button" aria-label="Bajar" disabled={n === items.length - 1} onClick={() => mover(n, 1)}>↓</button>
              </div>
              <div className="checklists-fields">
                <input aria-label={`Ítem ${n + 1}`} value={it.label} placeholder="Qué debe hacer o revisar el técnico"
                  onChange={(e) => cambiar(n, { label: e.target.value })} maxLength={500} />
                <div className="checklists-row">
                  <input aria-label="Sección" value={it.section ?? ""} placeholder="Sección (opcional)"
                    onChange={(e) => cambiar(n, { section: e.target.value || null })} maxLength={120} />
                  <select aria-label="Foto que exige" value={it.evidence_category ?? ""}
                    onChange={(e) => cambiar(n, { evidence_category: e.target.value || null, requires_evidence: !!e.target.value })}>
                    <option value="">Sin foto obligatoria</option>
                    {Object.entries(cat?.evidence_categories ?? {}).map(([k, v]) => <option key={k} value={k}>Foto: {v}</option>)}
                  </select>
                  <select aria-label="Solo si" value={it.condition_code ?? ""}
                    onChange={(e) => cambiar(n, { condition_code: e.target.value || null })}>
                    <option value="">Aplica siempre</option>
                    {Object.entries(cat?.installation_conditions ?? {}).map(([k, v]) => <option key={k} value={k}>Solo si: {v}</option>)}
                  </select>
                </div>
                <div className="checklists-row is-checks">
                  <label className="billing-check"><input type="checkbox" checked={it.is_required}
                    onChange={(e) => cambiar(n, { is_required: e.target.checked })} /> Obligatorio</label>
                  <label className="billing-check"><input type="checkbox" checked={!!it.allows_not_applicable}
                    onChange={(e) => cambiar(n, { allows_not_applicable: e.target.checked })} /> Permite «no aplica»</label>
                  <button type="button" className="acta-link checklists-remove" onClick={() => setItems((xs) => xs.filter((_, i) => i !== n))}>Quitar</button>
                </div>
              </div>
            </li>
          ))}
        </ol>
        <button type="button" className="acta-btn is-quiet" onClick={() => setItems((xs) => [...xs, vacio(xs.length + 1)])}>+ Agregar ítem</button>

        {error && <p className="form-error" role="alert">{error}</p>}
        {aviso && <p className="info-banner" role="status">{aviso}</p>}
        <div className="checklists-footer">
          {template && (
            <button type="button" className="acta-btn is-quiet review-danger" disabled={borrar.isPending}
              onClick={() => { if (window.confirm(programId ? "¿Borrar este checklist? El programa volverá a usar el por defecto." : "¿Borrar el checklist por defecto?")) borrar.mutate(); }}>
              Borrar checklist</button>
          )}
          <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending || !nombre.trim()}>
            {guardar.isPending ? "Guardando…" : "Guardar"}
          </button>
        </div>
      </form>
    </article>
  );
}
