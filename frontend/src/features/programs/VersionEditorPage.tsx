import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "./programs.css";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import type { Condition, DefinitionField, DefinitionStep, Evaluation, FieldOption } from "@/types/programs";
import {
  VERSION_STATUS,
  addStep,
  addStepField,
  deleteStep,
  deleteStepField,
  getVersion,
  listFields,
  listPrograms,
  listTerms,
  moveStep,
  moveStepField,
  previewVersion,
  programKeys,
  publishVersion,
  updateStepField,
  updateVersion,
  useProgramCatalogs,
} from "./api";
import { FormRenderer } from "./FormRenderer";
import { confirmAction } from "@/components/ui/ConfirmDialog";

/**
 * Editor de una versión del formulario del vendedor. A la izquierda los pasos
 * en orden con sus campos (subir/bajar, obligatoriedad, condición); a la
 * derecha la vista previa en vivo, evaluada por el mismo motor que usará la
 * pantalla del vendedor. Una versión publicada se ve pero no se edita.
 */
export function VersionEditorPage() {
  const { versionId } = useParams<{ versionId: string }>();
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const { data, isLoading } = useQuery({ queryKey: programKeys.version(versionId!), queryFn: () => getVersion(versionId!) });
  const { data: programas } = useQuery({ queryKey: programKeys.list, queryFn: listPrograms });
  const [error, setError] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: programKeys.version(versionId!) });
  const publicar = useMutation({
    mutationFn: () => publishVersion(versionId!),
    onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: programKeys.list }); return refresh(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  if (isLoading || !data) return <p>Cargando…</p>;
  const v = data.version;
  const programa = programas?.find((p) => p.id === v.program_id);
  const editable = v.status === "draft" && hasPermission("workflows.manage");
  const pasos = data.definition.steps;
  const totalCampos = pasos.reduce((a, s) => a + s.fields.length, 0);

  return (
    <div className="version-page">
      <Link to={`/programs?program=${v.program_id}`} className="acta-back"><span aria-hidden="true">‹</span> Volver a programas</Link>
      <article className="acta version-sheet">
        <header className="acta-header">
          <div className="acta-title-row">
            <h1 className="acta-title">{programa?.name ?? "Programa"} · formulario v{v.version}</h1>
            <span className={`billing-chip ${v.status === "published" ? "is-paid" : v.status === "draft" ? "is-draft" : "is-void"}`}>{VERSION_STATUS[v.status]}</span>
          </div>
          <dl className="acta-meta">
            <div><dt>Pasos</dt><dd>{pasos.length}</dd></div>
            <div><dt>Campos</dt><dd>{totalCampos}</dd></div>
            <div><dt>Fase</dt><dd>{data.phases.map((p) => p.name).join(", ")}</dd></div>
            <TermsPicker versionId={v.id} programId={v.program_id} termsId={v.terms_id} editable={editable} onChanged={refresh} />
          </dl>
          {v.status !== "draft" && (
            <p className="acta-note">Esta versión {v.status === "published" ? "está publicada" : "está archivada"} y no se edita.
              Para cambiar algo, crea una versión nueva desde el programa.</p>
          )}
        </header>
        {error && <p className="form-error" role="alert">{error}</p>}
        {v.status === "draft" && (
          <div className={`publish-bar${data.problems.length ? " has-problems" : ""}`}>
            {data.problems.length ? (
              <div><strong>Antes de publicar:</strong><ul>{data.problems.map((p) => <li key={p}>{p}</li>)}</ul></div>
            ) : <span>Lista para publicar. Los expedientes nuevos usarán esta versión; la anterior queda archivada.</span>}
            {hasPermission("workflows.publish") && (
              <button type="button" className="acta-btn is-primary" disabled={data.problems.length > 0 || publicar.isPending}
                onClick={() => publicar.mutate()}>{publicar.isPending ? "Publicando…" : "Publicar versión"}</button>
            )}
          </div>
        )}
      </article>

      <div className="version-layout">
        <section className="acta version-editor" aria-label="Pasos del formulario">
          <ol className="acta-steps">
            {pasos.map((paso, n) => (
              <StepCard key={paso.id} step={paso} index={n} total={pasos.length} editable={editable}
                allKeys={pasos.flatMap((s) => s.fields)} onChanged={refresh} onError={setError} />
            ))}
          </ol>
          {editable && data.phases[0] && <AddStep phaseId={data.phases[0].id} onChanged={refresh} onError={setError} />}
        </section>
        <Preview versionId={v.id} definitionKey={JSON.stringify(pasos)} />
      </div>
    </div>
  );
}

function TermsPicker({ versionId, programId, termsId, editable, onChanged }: {
  versionId: string; programId: string; termsId: string | null; editable: boolean; onChanged: () => void;
}) {
  const { data } = useQuery({ queryKey: programKeys.part(programId, "terms"), queryFn: () => listTerms(programId) });
  const cambiar = useMutation({ mutationFn: (id: string) => updateVersion(versionId, { terms_id: id || null }), onSuccess: onChanged });
  const actual = data?.find((t) => t.id === termsId);
  return (
    <div><dt>Términos</dt><dd>
      {editable ? (
        <select aria-label="Términos de esta versión" value={termsId ?? ""} onChange={(e) => cambiar.mutate(e.target.value)}>
          <option value="">Sin términos</option>
          {(data ?? []).filter((t) => t.published_at).map((t) => <option key={t.id} value={t.id}>{t.version} · {t.language}</option>)}
        </select>
      ) : actual ? `${actual.version} · ${actual.language}` : "Sin términos"}
    </dd></div>
  );
}

const REQ_LABEL = { required: "Obligatorio", optional: "Opcional", conditional: "Condicional" } as const;

function conditionText(c: Condition | null, campos: DefinitionField[]): string {
  if (!c) return "";
  const campo = campos.find((f) => f.key === c.field);
  const nombre = campo?.label ?? c.field;
  const etiqueta = (v: unknown) => campo?.options?.find((o) => o.value === v)?.label ?? String(v);
  if ("not_empty" in c) return `si «${nombre}» tiene respuesta`;
  if ("in" in c) return `si «${nombre}» es ${(c.in ?? []).map(etiqueta).join(" o ")}`;
  return `si «${nombre}» es ${etiqueta(c.eq)}`;
}

function StepCard({ step, index, total, editable, allKeys, onChanged, onError }: {
  step: DefinitionStep; index: number; total: number; editable: boolean; allKeys: DefinitionField[];
  onChanged: () => void; onError: (m: string | null) => void;
}) {
  const [abierto, setAbierto] = useState(index === 0);
  const act = <T,>(fn: (v: T) => Promise<unknown>) => ({
    mutationFn: fn, onSuccess: () => { onError(null); onChanged(); }, onError: (e: unknown) => onError(apiErrorMessage(e)),
  });
  const mover = useMutation(act((d: "up" | "down") => moveStep(step.id, d)));
  const quitar = useMutation(act(() => deleteStep(step.id)));
  const obligatorios = step.fields.filter((f) => f.requirement === "required").length;
  return (
    <li className={`acta-step ${abierto ? "is-current" : "is-pending"}`}>
      <span className="acta-step-marker" aria-hidden="true">{index + 1}</span>
      <div className="acta-step-head version-step-head">
        <button type="button" className="version-step-toggle" aria-expanded={abierto} onClick={() => setAbierto(!abierto)}>
          <span className="acta-step-title">{step.title}</span>
          <span className="acta-step-summary">{step.fields.length} campos · {obligatorios} obligatorios</span>
        </button>
        {editable && (
          <span className="acta-actions">
            <button type="button" className="icon-btn" aria-label="Subir paso" disabled={index === 0} onClick={() => mover.mutate("up")}>↑</button>
            <button type="button" className="icon-btn" aria-label="Bajar paso" disabled={index === total - 1} onClick={() => mover.mutate("down")}>↓</button>
            <button type="button" className="icon-btn" aria-label="Quitar paso"
              onClick={async () => { if (await confirmAction({ title: `¿Quitar el paso «${step.title}»?`, message: "Se quitan también sus campos de esta versión.", confirmLabel: "Quitar", danger: true })) quitar.mutate(undefined); }}>✕</button>
          </span>
        )}
      </div>
      {abierto && (
        <div className="acta-step-body"><div className="acta-step-card">
          <ul className="step-fields">
            {step.fields.map((f, i) => (
              <StepFieldRow key={f.id} field={f} index={i} total={step.fields.length} editable={editable}
                allKeys={allKeys} onChanged={onChanged} onError={onError} />
            ))}
          </ul>
          {step.fields.length === 0 && <p className="acta-empty">Sin campos.</p>}
          {editable && <AddField stepId={step.id} usedIds={allKeys.map((f) => f.field_id)} onChanged={onChanged} onError={onError} />}
        </div></div>
      )}
    </li>
  );
}

function StepFieldRow({ field: f, index, total, editable, allKeys, onChanged, onError }: {
  field: DefinitionField; index: number; total: number; editable: boolean; allKeys: DefinitionField[];
  onChanged: () => void; onError: (m: string | null) => void;
}) {
  const [editando, setEditando] = useState(false);
  const { data: cat } = useProgramCatalogs();
  const act = <T,>(fn: (v: T) => Promise<unknown>) => ({
    mutationFn: fn, onSuccess: () => { onError(null); onChanged(); }, onError: (e: unknown) => onError(apiErrorMessage(e)),
  });
  const mover = useMutation(act((d: "up" | "down") => moveStepField(f.id, d)));
  const quitar = useMutation(act(() => deleteStepField(f.id)));
  return (
    <li className="step-field">
      <div className="step-field-main">
        <strong>{f.label}</strong>
        <span className="step-field-meta">
          <span className="money">{f.key}</span> · {cat?.field_types[f.type] ?? f.type}
          {f.condition && <> · <em>{conditionText(f.condition, allKeys)}</em></>}
        </span>
      </div>
      <span className={`req-chip is-${f.requirement}`}>{REQ_LABEL[f.requirement]}</span>
      {editable && (
        <span className="acta-actions">
          <button type="button" className="icon-btn" aria-label="Subir" disabled={index === 0} onClick={() => mover.mutate("up")}>↑</button>
          <button type="button" className="icon-btn" aria-label="Bajar" disabled={index === total - 1} onClick={() => mover.mutate("down")}>↓</button>
          <button type="button" className="icon-btn" aria-label="Editar" onClick={() => setEditando(!editando)}>✎</button>
          <button type="button" className="icon-btn" aria-label="Quitar" onClick={() => quitar.mutate(undefined)}>✕</button>
        </span>
      )}
      {editando && <FieldRules field={f} allKeys={allKeys} onDone={() => { setEditando(false); onChanged(); }} onError={onError} />}
    </li>
  );
}

/** Obligatoriedad, condición y etiqueta propias del programa. */
function FieldRules({ field: f, allKeys, onDone, onError }: {
  field: DefinitionField; allKeys: DefinitionField[]; onDone: () => void; onError: (m: string | null) => void;
}) {
  const [req, setReq] = useState(f.requirement);
  const [label, setLabel] = useState(f.label);
  const [cond, setCond] = useState<Condition | null>(f.condition);
  const guardar = useMutation({
    mutationFn: () => updateStepField(f.id, { requirement: req, condition: req === "conditional" ? cond : null,
      label_override: label !== f.label ? label : undefined }),
    onSuccess: onDone, onError: (e) => onError(apiErrorMessage(e)),
  });
  return (
    <form className="program-inline-form field-rules" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <div className="field"><label htmlFor={`r-${f.id}`}>Obligatoriedad</label>
        <select id={`r-${f.id}`} value={req} onChange={(e) => setReq(e.target.value as DefinitionField["requirement"])}>
          <option value="required">Obligatorio</option><option value="optional">Opcional</option><option value="conditional">Condicional</option>
        </select></div>
      <div className="field"><label htmlFor={`l-${f.id}`}>Etiqueta en este programa</label>
        <input id={`l-${f.id}`} value={label} onChange={(e) => setLabel(e.target.value)} /></div>
      {req === "conditional" && <ConditionEditor value={cond} onChange={setCond} fields={allKeys.filter((x) => x.key !== f.key)} />}
      <div className="acta-actions program-span">
        <button type="button" className="acta-btn is-quiet" onClick={onDone}>Cancelar</button>
        <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>Guardar</button>
      </div>
    </form>
  );
}

function ConditionEditor({ value, onChange, fields }: {
  value: Condition | null; onChange: (c: Condition | null) => void; fields: DefinitionField[];
}) {
  const campo = fields.find((f) => f.key === value?.field);
  const opciones: FieldOption[] = campo?.type === "yes_no" ? [{ value: "yes", label: "Sí" }, { value: "no", label: "No" }] : campo?.options ?? [];
  const modo = value && "not_empty" in value ? "not_empty" : "eq";
  return (
    <div className="field program-span condition-editor">
      <label>Se muestra si</label>
      <div className="condition-row">
        <select aria-label="Campo del que depende" value={value?.field ?? ""}
          onChange={(e) => onChange(e.target.value ? { field: e.target.value, eq: "" } : null)}>
          <option value="">Elige el campo…</option>
          {fields.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
        </select>
        {value && (
          <select aria-label="Condición" value={modo}
            onChange={(e) => onChange(e.target.value === "not_empty" ? { field: value.field, not_empty: true } : { field: value.field, eq: "" })}>
            <option value="eq">es</option><option value="not_empty">tiene respuesta</option>
          </select>
        )}
        {value && modo === "eq" && (opciones.length ? (
          <select aria-label="Valor" value={String(value.eq ?? "")} onChange={(e) => onChange({ field: value.field, eq: e.target.value })}>
            <option value="">Elige…</option>
            {opciones.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ) : (
          <input aria-label="Valor" value={String(value.eq ?? "")} onChange={(e) => onChange({ field: value.field, eq: e.target.value })} />
        ))}
      </div>
    </div>
  );
}

function AddField({ stepId, usedIds, onChanged, onError }: {
  stepId: string; usedIds: string[]; onChanged: () => void; onError: (m: string | null) => void;
}) {
  const { data: campos } = useQuery({ queryKey: programKeys.fields, queryFn: listFields });
  const [abierto, setAbierto] = useState(false);
  const [campo, setCampo] = useState("");
  const [req, setReq] = useState("optional");
  const libres = (campos ?? []).filter((c) => c.active && !usedIds.includes(c.id));
  const agregar = useMutation({
    mutationFn: () => addStepField(stepId, { field_id: campo, requirement: req }),
    onSuccess: () => { onError(null); setCampo(""); setAbierto(false); onChanged(); },
    onError: (e) => onError(apiErrorMessage(e)),
  });
  if (!abierto) return <button type="button" className="acta-btn is-line" onClick={() => setAbierto(true)}>+ Agregar campo del catálogo</button>;
  return (
    <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); agregar.mutate(); }}>
      <div className="field program-span"><label htmlFor={`af-${stepId}`}>Campo</label>
        <select id={`af-${stepId}`} required value={campo} onChange={(e) => setCampo(e.target.value)}>
          <option value="">Elige un campo…</option>
          {libres.map((c) => <option key={c.id} value={c.id}>{c.section ? `${c.section} · ` : ""}{c.label}</option>)}
        </select></div>
      <div className="field"><label htmlFor={`ar-${stepId}`}>Obligatoriedad</label>
        <select id={`ar-${stepId}`} value={req} onChange={(e) => setReq(e.target.value)}>
          <option value="required">Obligatorio</option><option value="optional">Opcional</option>
        </select></div>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(false)}>Cancelar</button>
        <button type="submit" className="acta-btn is-primary" disabled={agregar.isPending}>Agregar</button>
      </div>
    </form>
  );
}

function AddStep({ phaseId, onChanged, onError }: { phaseId: string; onChanged: () => void; onError: (m: string | null) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [titulo, setTitulo] = useState("");
  const crear = useMutation({
    mutationFn: () => addStep(phaseId, { title: titulo }),
    onSuccess: () => { setTitulo(""); setAbierto(false); onError(null); onChanged(); },
    onError: (e) => onError(apiErrorMessage(e)),
  });
  if (!abierto) return <button type="button" className="acta-btn is-line" onClick={() => setAbierto(true)}>+ Agregar paso</button>;
  return (
    <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
      <div className="field program-span"><label htmlFor="ns-title">Título del paso</label>
        <input id="ns-title" required value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="Electrodomésticos" autoFocus /></div>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(false)}>Cancelar</button>
        <button type="submit" className="acta-btn is-primary" disabled={crear.isPending}>Agregar paso</button>
      </div>
    </form>
  );
}

/** Vista previa en vivo: lo que vería el vendedor con estas respuestas. */
function Preview({ versionId, definitionKey }: { versionId: string; definitionKey: string }) {
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [cliente, setCliente] = useState(false);
  const [evaluacion, setEvaluacion] = useState<Evaluation | null>(null);
  const [paso, setPaso] = useState<string | null>(null);
  const firma = useMemo(() => JSON.stringify(answers), [answers]);
  useEffect(() => {
    let vivo = true;
    const t = setTimeout(() => previewVersion(versionId, answers, !cliente).then((r) => vivo && setEvaluacion(r)).catch(() => undefined), 250);
    return () => { vivo = false; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionId, firma, cliente, definitionKey]);
  const actual = paso ?? evaluacion?.steps[0]?.code ?? null;
  return (
    <aside className="acta version-preview" aria-label="Vista previa del vendedor">
      <div className="preview-head">
        <h2>Vista previa</h2>
        <label className="billing-check"><input type="checkbox" checked={cliente} onChange={(e) => setCliente(e.target.checked)} /> Como lo ve el cliente</label>
      </div>
      {evaluacion && (
        <>
          <ol className="preview-steps">
            {evaluacion.steps.map((s, n) => (
              <li key={s.code}>
                <button type="button" className={`${s.code === actual ? "is-on" : ""}${s.complete ? " is-complete" : ""}`} onClick={() => setPaso(s.code)}>
                  {s.complete ? "✓" : n + 1}<span>{s.title}</span>
                </button>
              </li>
            ))}
          </ol>
          {actual && <FormRenderer evaluation={evaluacion} answers={answers} stepCode={actual} mediaPlaceholder
            onChange={(k, v) => setAnswers((a) => ({ ...a, [k]: v }))} />}
          <div className={`preview-status${evaluacion.can_submit ? " is-ok" : ""}`}>
            {evaluacion.can_submit ? "Todo completo: el vendedor podría enviar." : `Faltan ${evaluacion.missing.length} para poder enviar.`}
            <button type="button" className="acta-btn is-quiet" onClick={() => setAnswers({})}>Empezar de nuevo</button>
          </div>
        </>
      )}
    </aside>
  );
}
